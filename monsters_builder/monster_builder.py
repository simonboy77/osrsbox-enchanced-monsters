"""
Author:  PH01L
Email:   phoil@osrsbox.com
Website: https://www.osrsbox.com

Copyright (c) 2019, PH01L

###############################################################################
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
###############################################################################
"""

import json
import logging
from pathlib import Path

import jsonschema
import mwparserfromhell
from deepdiff import DeepDiff

import config
from extraction_tools_wiki import infobox_cleaner
from extraction_tools_wiki import wikitext_parser
from extraction_tools_wiki.wikitext_parser import WikitextTemplateParser
from osrsbox.monsters_api.monster_definition import MonsterDefinition

logger = logging.getLogger(__name__)


class BuildMonster:
    def __init__(self, monster_id, all_monster_cache_data, all_wikitext_processed,
                 all_wikitext_raw,  all_db_monster, all_db_items,
                 export_monster):
        self.monster_id = monster_id
        self.all_monster_cache_data = all_monster_cache_data  # Raw cache data for all monsters
        self.all_wikitext_processed = all_wikitext_processed  # Processed wikitext for all monsters
        self.all_wikitext_raw = all_wikitext_raw  # Raw data dump from OSRS Wiki
        self.all_db_monster = all_db_monster  # The existing monster database contents
        self.all_db_items = all_db_items  # The existing item database contents
        self.export_monster = export_monster  # If the JSON should be exported/created

        # For this monster instance, create dictionary for property storage
        self.monster_dict = dict()

        # For this monster instance, create an empty drops object
        self.drops = list()

        # Set some important properties used for monster building
        self.wiki_page_name = None  # The page name the wikitext is from
        self.infobox_version_number = None  # The version used on the wikitext page
        self.status = None  # Used if the item is special (invalid, normalized etc.)

        # All properties that are available for all items
        self.properties = [
            "id",
            "name",
            "incomplete"
            "members",
            "release_date",
            "combat_level",
            "hitpoints",
            "max_hit",
            "attack_type",
            "attack_speed",
            "aggressive",
            "poisonous",
            "immune_poison",
            "immune_venon",
            "weakness",
            "slayer_monster",
            "slayer_level",
            "slayer_xp",
            "slayer_masters",
            "examine",
            "wiki_name",
            "wiki_url",
            "attack_level",
            "strength_level",
            "defence_level",
            "magic_level",
            "ranged_level",
            "attack_stab",
            "attack_slash",
            "attack_crush",
            "attack_magic",
            "attack_ranged",
            "defence_stab",
            "defence_slash",
            "defence_crush",
            "defence_magic",
            "defence_ranged",
            "attack_accuracy",
            "melee_strength",
            "ranged_strength",
            "magic_damage",
            "drops",
            "rare_drop_table"]

    def generate_monster_object(self):
        """Generate the `MonsterDefinition` object from the monster_dict dictiornary."""
        self.monster_definition = MonsterDefinition(**self.monster_dict)

    def compare_new_vs_old_monster(self):
        """Compare the newly generated monster to the existing monster in the database."""
        self.compare_json_files(self.monster_definition)

    def export_monster_to_json(self):
        """Export monster to JSON, if requested."""
        if self.export_monster:
            output_dir = Path(config.DOCS_PATH, "monsters-json")
            self.monster_definition.export_json(True, output_dir)
        logging.debug(self.monster_dict)

    def preprocessing(self):
        """Preprocess an monster, and set important object variables.

        This function preprocesses every monster dumped from the OSRS cache. Various
        properties are set to help further processing. MORE."""
        # Set monster ID variables
        self.monster_id_int = int(self.monster_id)  # Monster ID number as an integer
        self.monster_id_str = str(self.monster_id)  # Monster ID number as a string

        # Load monster dictionary of cache data based on monster ID
        # This raw cache data is the baseline informaiton about the specific monster
        # and can be considered 100% correct and available for every monster
        self.monster_cache_data = self.all_monster_cache_data[self.monster_id_str]

        # Set monster name variable (directly from the cache dump)
        self.monster_name = self.monster_cache_data["name"]

        # Log and print monster
        logging.debug(f"======================= {self.monster_id_str} {self.monster_name}")
        # print(f"======================= {self.monster_id_str} {self.monster_name}")
        logging.debug(f"preprocessing: using the following cache data:")
        logging.debug(self.monster_cache_data)

        # Set all variables to None (for invalid monsters)
        self.monster_wikitext = None
        self.wikitext_found_using = None
        self.has_infobox = False

        # Try to find the wiki data using direct ID number search
        if self.all_wikitext_processed.get(self.monster_id_str, None):
            self.monster_wikitext = self.all_wikitext_processed.get(self.monster_id_str, None)
            self.wikitext_found_using = "id"

        # Try to find the wiki data using direct name search
        elif self.all_wikitext_raw.get(self.monster_name, None):
            self.monster_wikitext = self.all_wikitext_raw.get(self.monster_name, None)
            self.wikitext_found_using = "name"

        logging.debug(f"preprocessing: self.monster_wikitext found using: {self.wikitext_found_using}")

        # If there is no wikitext, and the monster is valid, raise a critical error
        if not self.monster_wikitext:
            logging.critical("CRITICAL: Could not find monster_wikitext by id or name...")
            return False

        # Parse the infobox monster
        infobox_parser = WikitextTemplateParser(self.monster_wikitext)

        # Try extract infobox for monster
        self.has_infobox = infobox_parser.extract_infobox("infobox monster")
        if not self.has_infobox:
            logging.critical("CRITICAL: Could not find template...")
            return False

        self.is_versioned = infobox_parser.determine_infobox_versions()
        logging.debug(f"preprocessing: Is the infobox versioned: {self.is_versioned}")
        self.versioned_ids = infobox_parser.extract_infobox_ids()
        logging.debug(f"preprocessing: Versioned IDs: {self.versioned_ids}")

        # Set the infobox version number, default to empty string (no version number)
        try:
            if self.versioned_ids:
                self.infobox_version_number = self.versioned_ids[self.monster_id_int]
        except KeyError:
            if self.is_versioned:
                self.infobox_version_number = "1"
            else:
                self.infobox_version_number = ""
        logging.debug(f"preprocessing: infobox_version_number: {self.infobox_version_number}")

        # Set the template
        self.template = infobox_parser.template

        return True

    def populate_monster(self):
        """Populate an monster after preprocessing it.

        This is called for every monster in the OSRS cache dump. Start by populating
        the raw metadata from the cache. Then ... MORE."""
        # Start by populatng the monster from the cache data
        self.populate_from_cache_data()
        self.populate_monster_properties_from_wiki_data()

    def populate_from_cache_data(self):
        """Populate a monster using raw cache data.

        This function takes the raw OSRS cache data for the specific monster and loads
        all available properties (that are extracted from the cache)."""
        # Log, then populate cache properties
        logging.debug("populate_from_cache: Loading item cache data data to object...")
        self.monster_dict["id"] = self.monster_cache_data["id"]
        self.monster_dict["name"] = self.monster_cache_data["name"]
        self.monster_dict["combat_level"] = self.monster_cache_data["combatLevel"]
        self.monster_dict["size"] = self.monster_cache_data["tileSpacesOccupied"]

    def populate_monster_properties_from_wiki_data(self):
        """Populate item data from a OSRS Wiki Infobox Item template."""
        logging.debug("populate_monster_properties_from_wiki_data: Populating wiki data...")

        # STAGE ONE: Determine then set the wiki_name and wiki_url

        # Manually set OSRS Wiki name
        if self.wikitext_found_using not in ["id"]:
            # Monster found in wiki by ID, cache name is the best option
            wiki_page_name = self.monster_name
        else:
            # Monster found using direct cache name lookup on wiki page names,
            # So use wiki page name in the monster_wikitext array
            wiki_page_name = self.monster_wikitext[0]

        wiki_versioned_name = None
        wiki_name = None

        # Get the versioned, or non-versioned, name from the infobox
        if self.infobox_version_number is not None:
            key = "version" + str(self.infobox_version_number)
            wiki_versioned_name = self.extract_infobox_value(self.template, key)
        else:
            wiki_versioned_name = self.extract_infobox_value(self.template, "version")

        # Set the wiki_name property
        if wiki_versioned_name is not None:
            if wiki_versioned_name.startswith("("):
                wiki_name = wiki_page_name + " " + wiki_versioned_name
            else:
                wiki_name = wiki_page_name + " (" + wiki_versioned_name + ")"
        else:
            wiki_name = wiki_page_name

        self.monster_dict["wiki_name"] = wiki_name

        # Set the wiki_url property
        if wiki_versioned_name is not None:
            wiki_url = wiki_page_name + "#" + wiki_versioned_name
        else:
            wiki_url = wiki_page_name

        wiki_url = wiki_url.replace(" ", "_")
        self.monster_dict["wiki_url"] = "https://oldschool.runescape.wiki/w/" + wiki_url

        # STAGE TWO: Extract, process and set monster properties from the infobox template

        # MEMBERS: Determine the members status of a monster
        members = None
        if self.infobox_version_number is not None:
            key = "members" + str(self.infobox_version_number)
            members = self.extract_infobox_value(self.template, key)
        if members is None:
            members = self.extract_infobox_value(self.template, "members")
        if members is not None:
            self.monster_dict["members"] = infobox_cleaner.clean_boolean(members)
        else:
            self.monster_dict["members"] = None
            self.monster_dict["incomplete"] = True

        # RELEASE_DATE: Determine the release date of a monster
        release_date = None
        if self.infobox_version_number is not None:
            key = "release" + str(self.infobox_version_number)
            release_date = self.extract_infobox_value(self.template, key)
        if release_date is None:
            release_date = self.extract_infobox_value(self.template, "release")
        if release_date is not None:
            self.monster_dict["release_date"] = infobox_cleaner.clean_release_date(release_date)
        else:
            self.monster_dict["release_date"] = None
            self.monster_dict["incomplete"] = True

        # HITPOINTS: Determine the hitpoints of a monster
        hitpoints = None
        if self.infobox_version_number is not None:
            key = "hitpoints" + str(self.infobox_version_number)
            hitpoints = self.extract_infobox_value(self.template, key)
        if hitpoints is None:
            hitpoints = self.extract_infobox_value(self.template, "hitpoints")
        if hitpoints is not None:
            self.monster_dict["hitpoints"] = infobox_cleaner.clean_integer(hitpoints)
        else:
            self.monster_dict["hitpoints"] = 0
            self.monster_dict["incomplete"] = True

        # MAX HIT: Determine the max hit of a monster
        max_hit = None
        if self.infobox_version_number is not None:
            key = "max hit" + str(self.infobox_version_number)
            max_hit = self.extract_infobox_value(self.template, key)
        if max_hit is None:
            max_hit = self.extract_infobox_value(self.template, "max hit")
        if max_hit is not None:
            self.monster_dict["max_hit"] = infobox_cleaner.clean_integer(max_hit)
        else:
            self.monster_dict["max_hit"] = 0
            self.monster_dict["incomplete"] = True

        # ATTACK TYPE: Determine the attack type of a monster
        attack_type = None
        if self.infobox_version_number is not None:
            key = "attack style" + str(self.infobox_version_number)
            attack_type = self.extract_infobox_value(self.template, key)
        if attack_type is None:
            attack_type = self.extract_infobox_value(self.template, "attack style")
        if attack_type is not None:
            self.monster_dict["attack_type"] = infobox_cleaner.clean_attack_type(attack_type)
        else:
            self.monster_dict["attack_type"] = list()
            self.monster_dict["incomplete"] = True

        # ATTACK SPEED: Determine the attack speed of a monster
        attack_speed = None
        if self.infobox_version_number is not None:
            key = "attack speed" + str(self.infobox_version_number)
            attack_speed = self.extract_infobox_value(self.template, key)
        if attack_speed is None:
            attack_speed = self.extract_infobox_value(self.template, "attack speed")
        if attack_speed is not None:
            self.monster_dict["attack_speed"] = infobox_cleaner.clean_integer(attack_speed)
        else:
            self.monster_dict["attack_speed"] = None
            self.monster_dict["incomplete"] = True

        # AGGRESSIVE: Determine the aggressive property of a monster
        aggressive = None
        if self.infobox_version_number is not None:
            key = "aggressive" + str(self.infobox_version_number)
            aggressive = self.extract_infobox_value(self.template, key)
        if aggressive is None:
            aggressive = self.extract_infobox_value(self.template, "aggressive")
        if aggressive is not None:
            self.monster_dict["aggressive"] = infobox_cleaner.clean_boolean(aggressive)
        else:
            self.monster_dict["aggressive"] = False
            self.monster_dict["incomplete"] = True

        # POISONOUS: Determine the poisonous property of a monster
        poisonous = None
        if self.infobox_version_number is not None:
            key = "poisonous" + str(self.infobox_version_number)
            poisonous = self.extract_infobox_value(self.template, key)
        if poisonous is None:
            poisonous = self.extract_infobox_value(self.template, "poisonous")
        if poisonous is not None:
            self.monster_dict["poisonous"] = infobox_cleaner.clean_boolean(poisonous)
        else:
            self.monster_dict["poisonous"] = False
            self.monster_dict["incomplete"] = True

        # IMMUNE POISON: Determine the immunity to poison property of a monster
        immune_poison = None
        if self.infobox_version_number is not None:
            key = "immunepoison" + str(self.infobox_version_number)
            immune_poison = self.extract_infobox_value(self.template, key)
        if immune_poison is None:
            immune_poison = self.extract_infobox_value(self.template, "immunepoison")
        if immune_poison is not None:
            self.monster_dict["immune_poison"] = infobox_cleaner.clean_boolean(immune_poison)
        else:
            self.monster_dict["immune_poison"] = False
            self.monster_dict["incomplete"] = True

        # IMMUNE VENOM: Determine the immunity to venon property of a monster
        immune_venom = None
        if self.infobox_version_number is not None:
            key = "immunevenom" + str(self.infobox_version_number)
            immune_venom = self.extract_infobox_value(self.template, key)
        if immune_venom is None:
            immune_venom = self.extract_infobox_value(self.template, "immunevenom")
        if immune_venom is not None:
            self.monster_dict["immune_venom"] = infobox_cleaner.clean_boolean(immune_venom)
        else:
            self.monster_dict["immune_venom"] = False
            self.monster_dict["incomplete"] = True

        # WEAKNESS: Determine any weaknesses of the monster
        weakness = None
        if self.infobox_version_number is not None:
            key = "weakness" + str(self.infobox_version_number)
            weakness = self.extract_infobox_value(self.template, key)
        if weakness is None:
            weakness = self.extract_infobox_value(self.template, "weakness")
        if weakness is not None:
            weakness = infobox_cleaner.clean_weaknesses(weakness)
            self.monster_dict["weakness"] = weakness
        else:
            self.monster_dict["weakness"] = list()
            self.monster_dict["incomplete"] = True

        # SLAYER LEVEL: Determine the slayer level required
        slayer_level = None
        if self.infobox_version_number is not None:
            key = "slaylvl" + str(self.infobox_version_number)
            slayer_level = self.extract_infobox_value(self.template, key)
        if slayer_level is None:
            slayer_level = self.extract_infobox_value(self.template, "slaylvl")
        if slayer_level is not None:
            self.monster_dict["slayer_level"] = infobox_cleaner.clean_integer(slayer_level)
        else:
            self.monster_dict["slayer_level"] = None
            self.monster_dict["incomplete"] = True

        # SLAYER XP: Determine XP given from slayer monster kill
        slayer_xp = None
        if self.infobox_version_number is not None:
            key = "slayxp" + str(self.infobox_version_number)
            slayer_xp = self.extract_infobox_value(self.template, key)
        if slayer_xp is None:
            slayer_xp = self.extract_infobox_value(self.template, "slayxp")
        if slayer_xp is not None:
            self.monster_dict["slayer_xp"] = infobox_cleaner.clean_integer(slayer_xp)
        else:
            self.monster_dict["slayer_xp"] = None
            self.monster_dict["incomplete"] = True

        # SLAYER MONSTER: Determine if the monster can be a slayer task
        if self.monster_dict["slayer_level"]:
            self.monster_dict["slayer_monster"] = True
        else:
            self.monster_dict["slayer_monster"] = False

        # SLAYER MASTERS: Determine the slayer masters
        if self.monster_dict["slayer_monster"]:
            # Populate a list of slayer masters
            # This name is used by this project and the OSRS Wiki
            slayer_masters = ["turael",
                              "krystilia",
                              "mazchna",
                              "vannaka",
                              "chaeldar",
                              "konar",
                              "nieve",
                              "duradel"
                              ]

            # Loop through each slayer master and add to a list if the slayer
            # master assigns this monster as a slayer task
            value_list = list()
            for slayer_master in slayer_masters:
                value = None
                if self.infobox_version_number is not None:
                    key = slayer_master + str(self.infobox_version_number)
                    value = self.extract_infobox_value(self.template, key)
                if value is None:
                    value = self.extract_infobox_value(self.template, slayer_master)
                if value is not None:
                    value_list.append(slayer_master)
                self.monster_dict["slayer_masters"] = value_list

        # Set the slayer_masters property to an empty list if not populated
        try:
            if not self.monster_dict["slayer_masters"]:
                self.monster_dict["slayer_masters"] = list()
        except KeyError:
            self.monster_dict["slayer_masters"] = list()

        # EXAMINE: Determine the monster examine text
        examine = None
        if self.infobox_version_number is not None:
            key = "examine" + str(self.infobox_version_number)
            examine = self.extract_infobox_value(self.template, key)
        if examine is None:
            examine = self.extract_infobox_value(self.template, "examine")
        if examine is not None:
            self.monster_dict["examine"] = infobox_cleaner.clean_monster_examine(examine)
        else:
            self.monster_dict["examine"] = None
            self.monster_dict["incomplete"] = True

        # MONSTER COMBAT BONUSES: Determine stats of the monster

        # Initialize a dictionary that maps database_name -> infobox_name
        # The database_name is used in this project
        # The infobox_name is used by the OSRS Wiki
        combat_bonuses = {"attack_level": "att",
                          "strength_level": "str",
                          "defence_level": "def",
                          "magic_level": "mage",
                          "ranged_level": "range",
                          "attack_stab": "astab",
                          "attack_slash": "aslash",
                          "attack_crush": "acrush",
                          "attack_magic": "amagic",
                          "attack_ranged": "arange",
                          "defence_stab": "dstab",
                          "defence_slash": "dslash",
                          "defence_crush": "dcrush",
                          "defence_magic": "dmagic",
                          "defence_ranged": "drange",
                          "attack_accuracy": "attbns",
                          "melee_strength": "strbns",
                          "ranged_strength": "rngbns",
                          "magic_damage": "mbns"
                          }

        # Loop each of the combat bonuses and populate
        for database_name, property_name in combat_bonuses.items():
            value = None
            if self.infobox_version_number is not None:
                key = property_name + str(self.infobox_version_number)
                value = self.extract_infobox_value(self.template, key)
            if value is None:
                value = self.extract_infobox_value(self.template, property_name)
            if value is not None:
                self.monster_dict[database_name] = infobox_cleaner.clean_stats_value(value)
            else:
                self.monster_dict[database_name] = 0
                self.monster_dict["incomplete"] = True

        # We finished processing, set incomplete to false if not true
        if not self.monster_dict.get("incomplete"):
            self.monster_dict["incomplete"] = False

    def extract_dropsline_header(self, table_head_type: str) -> float:
        """Parse the dropstablehead template for variable drop rarity values.

        :param table_head_type: Specify a seed, or herb table head search.
        :return: A float of the drop rarity multiplier.
        """
        # Extract "dropstablehead" templates
        # This is used for extracting "herbbase" and "seedbase" values
        self.drops_templates = wikitext_parser.extract_wikitext_template(self.monster_wikitext, "dropstablehead")

        table_head_value = None

        # Loop the found "dropstablehead" templates
        for template in self.drops_templates:
            # Parse the template
            template_parser = WikitextTemplateParser(self.monster_wikitext)
            template_parser.template = template
            if "vardefine:" + table_head_type in template:
                # Example:
                # {{DropsTableHead{{#vardefine:herbbase|{{#expr:9/123/128}}}}}}
                table_head_value = template.split("#expr:")[1]
                table_head_value = table_head_value.replace("}", "")
                table_head_value = eval(table_head_value)
                return table_head_value

    def parse_monster_drops(self):
        """Extract monster drop information.

        This function parses the monsters wiki page (raw wikitext), and extracts
        any MediaWiki template with the name "dropsline". Each template is processed
        to determine the ID, name, quantity, rarity and and requirements of the
        specific drop. Finally, the raw wikitext for the monster is parsed to
        determine if the monster has access to the rare drop table.
        """
        # Extract "dropsline" templates
        self.drops_templates = wikitext_parser.extract_wikitext_template(self.monster_wikitext, "dropsline")

        # Loop the found "dropsline" templates
        for template in self.drops_templates:
            # Parse the template
            template_parser = WikitextTemplateParser(self.monster_wikitext)
            template_parser.template = template

            # Initialize a null value dictionary for each item drop
            drop_dict = {
                "id": None,
                "name": None,
                "members": None,
                "quantity": None,
                "rarity": None,
                "drop_requirements": None
            }

            # Extract the drop information...

            # Extract the item drop name
            name = template_parser.extract_infobox_value("Name")

            # Skip any drop line with rare drop table
            if name.lower() == "rare drop table":
                continue

            # Determine the drop ID
            id = None
            found = False
            for item in self.all_db_items:
                if item.name == name or item.wiki_name == name:
                    found = True
                    id = item.id
                    break
            if not found:
                id = None

            # Extract the item drop quantity and if the drop is noted
            quantity = template_parser.extract_infobox_value("Quantity")
            noted = False
            if quantity:
                if "noted" in quantity.lower():
                    noted = True
            quantity = infobox_cleaner.clean_drop_quantity(quantity)

            # Extract, or determine, if the item is members-only
            members = False
            name_notes = template_parser.extract_infobox_value("Namenotes")
            if self.monster_dict["members"]:
                members = True
            elif id:
                if self.all_db_items[id].members:
                    members = True
            elif name_notes:
                if "{{m}}" in name_notes:
                    members = True

            # Extract the item drop rarity
            rarity = template_parser.extract_infobox_value("Rarity")
            base_value = None
            # If the item drop has a drop variable, fetch it
            if rarity:
                if "var:herbbase" in rarity:
                    base_value = self.extract_dropsline_header("herbbase")
                elif "var:seedbase" in rarity:
                    base_value = self.extract_dropsline_header("seedbase")
            rarity = infobox_cleaner.clean_drop_rarity(rarity, base_value)

            # Extract the rarity notes
            drop_requirements = template_parser.extract_infobox_value("Raritynotes")
            drop_requirements = infobox_cleaner.clean_drop_requirements(drop_requirements)

            # Populate the dictionary
            drop_dict = {
                "id": id,
                "name": name,
                "members": members,
                "quantity": quantity,
                "noted": noted,
                "rarity": rarity,
                "drop_requirements": drop_requirements
            }

            # Attach drops dict to the drops list for this monster
            self.drops.append(drop_dict)

        # Append the drops to the monster dictionary
        self.monster_dict["drops"] = self.drops

        # Determine if monster has access to the rare drop table
        if "{{raredroptable" in self.monster_wikitext[2].lower():
            self.monster_dict["rare_drop_table"] = True
        elif "{{gemdroptable" in self.monster_wikitext[2].lower():
            self.monster_dict["rare_drop_table"] = True
        else:
            self.monster_dict["rare_drop_table"] = False

    def extract_infobox_value(self, template: mwparserfromhell.nodes.template.Template, key: str) -> str:
        """Helper method to extract a value from a template using a specified key.

        This helper method is a simple solution to repeatedly try to fetch a specific
        entry from a wiki text template (a mwparserfromhell template object).

        :param template: A mediawiki wiki text template.
        :param key: The key to query in the template.
        :return value: The extracted template value based on supplied key.
        """
        value = None
        try:
            value = template.get(key).value
            value = value.strip()
            return value
        except ValueError:
            return value

    def compare_json_files(self, monster_definition: MonsterDefinition) -> bool:
        """Print the difference between this monster object, and the monster that exists in the database."""
        # Create JSON out object to compare
        current_json = monster_definition.construct_json()
        current_drops = current_json["drops"]
        del current_json["drops"]

        # Try get existing entry (KeyError means it doesn't exist - aka a new monster)
        try:
            existing_json = self.all_db_monster[self.monster_id]
            existing_drops = existing_json["drops"]
            del existing_json["drops"]
        except KeyError:
            print(f">>> compare_json_files: NEW MONSTER: {monster_definition.id}")
            print(current_json)
            return

        # Quick check of eqaulity, return if properties and drops are the same
        if current_json == existing_json:
            if current_drops == existing_drops:
                return

        # Print a header for the changed monster
        logging.debug(f">>> compare_json_files: CHANGED MONSTER: {monster_definition.id}: {monster_definition.name}, {monster_definition.wiki_name}")
        print(f">>> compare_json_files: CHANGED MONSTER: {monster_definition.id}: {monster_definition.name}")

        # First check the base properties
        ddiff_props = DeepDiff(existing_json, current_json, ignore_order=True)
        if ddiff_props:
            print("  > CHANGED BASE PROPERTIES...")
            print(ddiff_props)

        ddiff_drops = DeepDiff(existing_drops, current_drops, ignore_order=True)
        if ddiff_drops:
            print("  > CHANGED DROP PROPERTIES...")
            if ddiff_drops.get("iterable_item_added"):
                del ddiff_drops["iterable_item_added"]
            if ddiff_drops.get("iterable_item_removed"):
                del ddiff_drops["iterable_item_removed"]
            if ddiff_drops:
                print(ddiff_drops)

        return

    def validate_monster(self):
        """Use the monsters-schema.json file to validate the populated monster."""
        # Create JSON out object to validate
        current_json = self.monster_definition.construct_json()

        # Open the JSON Schema for monsters
        path_to_schema = Path(config.TEST_PATH / "monster_schema.json")
        with open(path_to_schema, 'r') as f:
            schema = json.loads(f.read())

        # Check the populate monster object against the schema
        jsonschema.validate(instance=current_json, schema=schema)

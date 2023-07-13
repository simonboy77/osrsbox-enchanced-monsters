#!/bin/bash
: '
Author:  PH01L
Email:   phoil@osrsbox.com
Website: https://www.osrsbox.com

Update files and run tests.

Copyright (c) 2021, PH01L

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
'
odb=$(cd ../..; pwd)

export PYTHONPATH="$(dirname "$(dirname "$(pwd)")")"

cd $odb
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

echo -e ">>> Updating project data..."
echo -e "  > monsters..."
cd $odb/scripts/monsters
#python3 update.py

echo -e ">>> Updating monster database"
rm -R $odb/docs/monsters-json/
mkdir $odb/docs/monsters-json/

cd $odb/builders/monsters/
python3 builder.py --export=True

echo -e ">>> Running JSON population scripts..."
cd $odb/scripts/update/
python3 update_monsters_custom.py

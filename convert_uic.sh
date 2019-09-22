for ui in $(ls *.ui)
do
	echo $ui
	name=$(echo $ui | cut -d. -f 1)
	pyuic5 $name.ui -o $name.py
done

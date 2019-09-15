in order to execute aSleaZyn, you have to (have PyQt5 and) have set QT_PLUGIN_PATH, QT_QPA_PLATFORM_PLUGIN_PATH and LD_LIBRARY_PATH, e.g. in my case:

	export QT_PLUGIN_PATH=/usr/lib64/qt5/plugins/
	export QT_QPA_PLATFORM_PLUGIN_PATH=/usr/lib64/qt5/plugins
	export LD_LIBRARY_PATH=/usr/lib64

also, you have to have a copy of

	./ma2_synatize.py
	./template.matzethemightyemperor

these are part of aMaySyn, fetch from

	https://github.com/qm210/aMaySyn

if you have done so, you should be able to call aSleaZyn via

	./aSleaZyn.py

or maybe you have to adjust the path to your python interpreter (if it is not #!/bin/usr/python3).

enjoy. the UI, especially :P

- QM / Team210

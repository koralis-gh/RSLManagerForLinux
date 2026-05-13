install:
	python3 -m pip install -r requirements.txt

run:
	python3 gui.py

check:
	python3 -m py_compile config.py process.py gui.py

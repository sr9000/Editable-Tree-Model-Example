lint:
	autoflake .
	isort . --extend-skip mainwindow.py
	black . --line-length 120 --extend-exclude mainwindow.py

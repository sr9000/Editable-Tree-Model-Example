lint:
	autoflake .
	isort .
	black --line-length 120 .

.PHONY: setup analysis notebook all clean

setup:
	python scripts/build_database.py

analysis: setup
	python scripts/run_analysis.py

notebook: analysis
	jupyter nbconvert --to notebook --execute notebooks/ecommerce_analysis.ipynb --output ecommerce_analysis.ipynb --output-dir notebooks --ExecutePreprocessor.timeout=300

all: notebook

clean:
	python scripts/clean_generated.py


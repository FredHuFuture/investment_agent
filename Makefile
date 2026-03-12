.PHONY: install install-all seed run run-backend run-frontend test demo clean

install:
	pip install --pre -e ".[dev]"
	cd frontend && npm install

install-all:
	pip install --pre -e ".[all]"
	cd frontend && npm install

seed:
	python seed.py

run-backend:
	uvicorn api.app:app --port 8000 --reload

run-frontend:
	cd frontend && npm run dev

run:
	@echo "Starting backend (port 8000) and frontend (port 3000)..."
	@echo "Press Ctrl+C to stop both."
	$(MAKE) run-backend & $(MAKE) run-frontend

test:
	python -m pytest tests/ -q

demo:
	python demo.py

clean:
	rm -f data/*.db data/*.db-wal data/*.db-shm
	rm -rf frontend/dist frontend/node_modules
	rm -rf __pycache__ .pytest_cache

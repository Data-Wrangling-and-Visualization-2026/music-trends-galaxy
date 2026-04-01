"""

Create all SQLAlchemy tables if they do not exist (schema only).

Does not import CSV/JSON from storage — that is handled by manual script runs.

"""



import sys

from pathlib import Path



ROOT = Path(__file__).resolve().parent.parent

sys.path.insert(0, str(ROOT))



from app.database import Base, engine

from app import models



if __name__ == "__main__":

    Base.metadata.create_all(bind=engine)

    print("Tables OK (create_all).")


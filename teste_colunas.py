from dotenv import load_dotenv
load_dotenv(override=True)

from core import db

sql = """
SELECT table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
ORDER BY table_name, ordinal_position
"""

print(db.executar(sql))

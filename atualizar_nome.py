import sqlite3

conn = sqlite3.connect('openfinance.db')
conn.execute("UPDATE bancos SET nome = 'Clara Bank' WHERE id = 1")
conn.commit()
conn.close()
print('Nome atualizado com sucesso!')
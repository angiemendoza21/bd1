import pyodbc

class BD:
    def __init__(self):
        self.conn = pyodbc.connect(
            'Driver={SQL Server};'
            'Server=LAPTOP-DAYANNA\\SQLEXPRESS;'   # <-- AJUSTA TU SERVIDOR
            'Database=BD1;'
            'Trusted_Connection=yes;'
        )
        self.cursor = self.conn.cursor()

    def query(self, sql):
        self.cursor.execute(sql)
        return self.cursor.fetchall()

    def execute(self, sql):
        self.cursor.execute(sql)
        self.conn.commit()

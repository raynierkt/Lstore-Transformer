from lstore.table import Table

class Database():

    def __init__(self):
        self.tables = []
        self.bufferpool = buffer_pool()

    def open(self, path):
        pass

    def close(self):
        pass

    """
    # Creates a new table
    :param name: string         #Table name
    :param num_columns: int     #Number of Columns: all columns are integer
    :param key: int             #Index of table key in columns
    """
    def create_table(self, name, num_columns, key):
        table = Table(name, num_columns, key)
        # create a new table in database
        self.tables.append(table)
        return table

    """
    # Deletes the specified table
    """
    def drop_table(self, name):
        if name in self.tables:
            self.tables.remove(name)
        else:
            pass

    """
    # Returns table with the passed name
    """
    def get_table(self, name):
        pass
from lstore.config import *

class Page:

    def __init__(self):
        self.num_records = 0
        self.data = bytearray(4096)

    def has_capacity(self):
        return self.num_records < MAX_RECORDS

    """
    :param value: int  #
    """
    def write(self, value):
        self.data[self.num_records * 8 : (self.num_records+1) * 8] = (value).to_bytes(8, byteorder='big')
        self.num_records += 1

    def get(self, index):
        return self.data[index*8 : (index+1)*8]

    def update(self, index, value):
        self.data[index * 8 : (index+1) * 8] = (value).to_bytes(8, byteorder='big')
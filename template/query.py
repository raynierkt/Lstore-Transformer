from template.table import Table, Record
from template.index import Index
from template.page import Page
from template.config import *
from copy import copy
import re
from time import time
from functools import reduce
from operator import add
# TODO: Change RID to all integer and set offset bit 
# TODO : implement all queries by indexing 
# TODO : implement page range 
# TODO : support non primary key selection 


class Query:
    """
    # Creates a Query object that can perform different queries on the specified table
    """

    def __init__(self, table):
        self.table = table
        self.index = Index(self.table)
        self.page_pointer = [0,0]
        pass 

    """
    # Insert a record with specified columns
    # param *columns: list of integers      # contain list of (key,value) of record
    """

    def insert(self, *columns):
        columns = list(columns)
        rid = int.from_bytes(('b'+ str(self.table.num_records)).encode(), byteorder = "big")
        schema_encoding = 0
        # INDIRECTION+RID+SCHEMA_ENCODING
        meta_data = [MAXINT,rid,schema_encoding]
        columns = list(columns)
        meta_data.extend(columns)
        base_data = meta_data
        for i, value in enumerate(base_data):
            page = self.table.page_directory["Base"][i][-1]
            # Verify Page is not full
            if not page.has_capacity():
                self.table.page_directory["Base"][i].append(Page())
                page = self.table.page_directory["Base"][i][-1]
            page.write(value)
        # update indices 
        self.page_pointer = [self.table.num_records//MAX_RECORDS,self.table.num_records%MAX_RECORDS]
        self.index.update_index(columns[self.table.key],self.page_pointer,self.table.key)
        # record_page_index,record_index = self.table.get(columns[self.table.key])
        # if (self.page_pointer != [record_page_index,record_index]):
        #     print("error message"+str(self.page_pointer) + str([record_page_index,record_index]))
        self.table.num_records += 1

    """
    # Read a record with specified key
    """
    def select(self, key, query_columns):
        # Get the indirection id given choice of primary keys
        page_pointer = self.index.locate(self.table.key,key)
        indirect_page = self.table.page_directory["Base"][INDIRECTION_COLUMN]
        indirect_byte =  indirect_page[page_pointer[0]].get(page_pointer[1]) # in bytes
        # Total record specified by key and columns : TA tester consider non-primary key 
        records, res = [], []
        schema_encoding = int.from_bytes(self.table.get_schema_encoding(key),byteorder="big")
        for query_col, val in enumerate(query_columns):
            # column is not selected
            if val != 1:
                res.append(None)
                continue
            # print(schema_encoding)
            if (schema_encoding & (1<<query_col))>>query_col == 1:
                # print("Column {} Modified. Read from Tail".format(query_col))
                page_tid, rec_tid = self.table.get_tail(indirect_byte)
                res.append(int.from_bytes(self.table.page_directory["Tail"][query_col + NUM_METAS][page_tid].get(rec_tid), byteorder="big"))
            else:
                # print("Column {} Not Modified. Read from Head".format(query_col))
                page_rid, rec_rid = self.table.get(key)
                res.append(int.from_bytes(self.table.page_directory["Base"][query_col + NUM_METAS][page_rid].get(rec_rid), byteorder="big"))
        record = Record(self.table.key_to_rid(key).decode(),key,res)
        records.append(record)
        return records

    """
    # Update a record with specified key and columns
    """
    def update(self, key, *columns):
        # get the indirection in base pages given specified key
        page_pointer = self.index.locate(self.table.key,key)
        update_record_page_index,update_record_index = page_pointer[0],page_pointer[1]
        indirect_page = self.table.page_directory["Base"][INDIRECTION_COLUMN]
        base_indirection_id =  indirect_page[update_record_page_index].get(update_record_index) # in bytes
        for query_col,val in enumerate(columns):
            if val == None:
                continue
            else:
                # compute new tail record TID
                next_tid = int.from_bytes(('t'+ str(self.table.num_updates)).encode(), byteorder = "big")
                # the record is firstly updated
                if (int.from_bytes(base_indirection_id,byteorder='big') == MAXINT):
                    # compute new tail record indirection :  the indirection of tail record point backward to base pages
                    rid_page = self.table.page_directory["Base"][RID_COLUMN]
                    next_tail_indirection =  rid_page[update_record_page_index].get(update_record_index) # in bytes
                    next_tail_indirection = int.from_bytes(next_tail_indirection,byteorder='big')
                    # compute tail columns : e.g. [NONE,NONE,updated_value,NONE]
                    next_tail_columns = []
                    next_tail_columns = [MAXINT for i in range(0,len(columns))]
                    next_tail_columns[query_col] = val

                # the record has been updated
                else:
                    # compute new tail record indirection : the indirection of new tail record point backward to last tail record for this key
                    next_tail_indirection = int.from_bytes(base_indirection_id,byteorder='big')
                    # compute tail columns : first copy the columns of the last tail record and update the new specified attribute
                    next_tail_columns = self.table.get_tail_columns(base_indirection_id)
                    next_tail_columns[query_col] = val
                # !!!: Need to do the encoding for lastest update
                encoding_page = self.table.page_directory["Base"][SCHEMA_ENCODING_COLUMN]
                encoding_base =  encoding_page[update_record_page_index].get(update_record_index) # in bytes
                old_encoding = int.from_bytes(encoding_base,byteorder="big")
                new_encoding = old_encoding | (1<<query_col)
                schema_encoding = new_encoding
                # update new tail record
                meta_data = [next_tail_indirection,next_tid,schema_encoding]
                meta_data.extend(next_tail_columns)
                tail_data = meta_data
                for col_id, col_val in enumerate(tail_data):
                    page = self.table.page_directory["Tail"][col_id][-1]
                    # Verify tail Page is not full
                    if not page.has_capacity():
                        self.table.page_directory["Tail"][col_id].append(Page())
                        page = self.table.page_directory["Tail"][col_id][-1]
                    # print("column: ", col_id)
                    # print("value update on the tail: ", col_val)
                    page.write(col_val)
                # overwrite base page with new metadata
                self.table.page_directory["Base"][INDIRECTION_COLUMN][update_record_page_index].update(update_record_index, next_tid)
                self.table.page_directory["Base"][SCHEMA_ENCODING_COLUMN][update_record_page_index].update(update_record_index, schema_encoding)
                self.table.num_updates += 1
            
    """
    :param start_range: int         # Start of the key range to aggregate
    :param end_range: int           # End of the key range to aggregate
    :param aggregate_columns: int   # Index of desired column to aggregate
    """

    def sum(self, start_range, end_range, aggregate_column_index):
        start_time = time()
        self.index.create_index(aggregate_column_index)
        values = self.index.locate_range(start_range, end_range, aggregate_column_index)
        if values != []:
            values = sum(reduce(add, values))        
        else:
            values = 0
        # print("Index Time: {}".format(time() - start_time))
        return values

    """
    # internal Method
    # Read a record with specified RID
    """

    def delete(self, key):
        page_index, record_index = self.table.get(key)
        self.table.invalidate_rid(page_index, record_index)
        #TODO: go through the indirection and invalidate all the tale records rid
        #TODO: need testing
        indirect_page = self.table.page_directory["Base"][INDIRECTION_COLUMN]
        indirect_tail_page = self.table.page_directory["Tail"][INDIRECTION_COLUMN]
        byte_indirect = indirect_page[page_index].get(record_index)
        if byte_indirect != MAXINT.to_bytes(8,byteorder = "big"):
            string_indirect = byte_indirect.decode()
            tail_page_index, tail_record_index = self.table.get_tail(byte_indirect)
            self.table.invalidate_tid(tail_page_index, tail_record_index)
            tail_byte_indirect = indirect_tail_page[tail_page_index].get(tail_record_index)
            tail_string_indirect = tail_byte_indirect.decode()
            while 'b' not in tail_string_indirect:
                tail_page_index, tail_record_index = self.table.get_tail(tail_byte_indirect)
                self.table.invalidate_tid(tail_page_index, tail_record_index)
                tail_byte_indirect = indirect_tail_page[tail_page_index].get(tail_record_index)
                if tail_byte_indirect != MAXINT.to_bytes(8,byteorder = "big"):
                    tail_string_indirect = tail_byte_indirect.decode()
                #print(tail_string_indirect)
            tail_page_index, tail_record_index = self.table.get_tail(tail_byte_indirect)
            self.table.invalidate_tid(tail_page_index, tail_record_index)
                #print(string_indirect)
                #if 'b' in tail_string_indirect:
                #    break;
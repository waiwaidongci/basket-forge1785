import csv,io
from fastapi.responses import Response
def _cell(value): return ("'"+str(value)) if isinstance(value,str) and value.startswith(('=','+','-','@')) else value
def csv_response(filename,rows,headers,notes=None):
 out=io.StringIO();writer=csv.writer(out)
 for line in notes or []: writer.writerow([_cell(v) for v in line])
 writer.writerow(headers)
 for values in rows:
  writer.writerow([_cell(v) for v in values])
 return Response('﻿'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="{filename}"'})

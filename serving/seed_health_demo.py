"""Seed a few C-MAPSS engine trajectories into VehicleTelemetry as stand-in vehicles
so the health pipeline has valid 21-sensor windows. Run locally once.
Requires: pip install boto3 pandas ; AWS creds configured (region us-east-1).
"""
import pandas as pd, boto3
from decimal import Decimal
sens=[f"s_{i}" for i in range(1,22)]
cols=["unit","cycle","setting_1","setting_2","setting_3"]+sens
test=pd.read_csv("data/test_FD001.txt",sep=r"\s+",header=None,names=cols)
tbl=boto3.resource("dynamodb",region_name="us-east-1").Table("VehicleTelemetry")
with tbl.batch_writer() as bw:
    for uid in range(1,6):                      # engines 1..5 -> engine-001..005
        d=test[test.unit==uid].sort_values("cycle").tail(30)
        vid=f"engine-{uid:03d}"
        for _,row in d.iterrows():
            item={"vehicle_id":vid,"timestamp":f"{int(row.cycle):04d}"}
            for s in sens: item[s]=Decimal(str(round(float(row[s]),4)))
            bw.put_item(Item=item)
        print("seeded",vid,len(d),"cycles")
print("done")

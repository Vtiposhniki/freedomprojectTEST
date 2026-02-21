import pandas as pd

m = pd.read_csv("managers.csv")

kar = m[m["Офис"] == "Караганда"]
print(kar[["ФИО","Навыки"]])
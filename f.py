def f():
    1 / 0

try:
    f()
except Exception as error:
    print(error)


import bpy

def test_operator():
    try:
        bpy.ops.my_addon.test_operator()
        print("Operator ran successfully")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_operator()

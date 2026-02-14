from src.parser import CodeParser

def debug_dart_methods():
    parser = CodeParser()
    if 'dart' not in parser.parsers:
        return

    dart_code = """
    class MyWidget {
      void build() {
        print("hello");
      }
      
      int get value => 5;
    }
    """
    
    p = parser.parsers['dart']
    tree = p.parse(bytes(dart_code, "utf8"))
    
    root = tree.root_node
    # Navigate to class body
    # program -> class_definition -> class_body
    for child in root.children:
        if child.type == 'class_definition':
            # find class_body
            body = next((c for c in child.children if c.type == 'class_body'), None)
            if body:
                print("Class Body Children:")
                for member in body.children:
                    print(f"  Type: {member.type}")

if __name__ == "__main__":
    debug_dart_methods()

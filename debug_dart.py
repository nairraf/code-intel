from src.parser import CodeParser

def debug_dart():
    parser = CodeParser()
    if 'dart' not in parser.parsers:
        return

    dart_code = """
    int globalFunc() {
      return 1;
    }
    """
    
    p = parser.parsers['dart']
    tree = p.parse(bytes(dart_code, "utf8"))
    
    root = tree.root_node
    
    for child in root.children:
        print(f"Node: {child.type}")
        if child.type == 'function_signature':
            sib = child.next_sibling
            print(f"  Next Sibling: {sib.type if sib else 'None'}")
            if sib and sib.type == 'function_body':
                print(f"  Combined Range: {child.start_byte}-{sib.end_byte}")
                combined_text = dart_code.encode('utf-8')[child.start_byte:sib.end_byte].decode('utf-8')
                print(f"  Combined Text: {combined_text}")

if __name__ == "__main__":
    debug_dart()

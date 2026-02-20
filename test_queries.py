import tree_sitter_python
from tree_sitter import Language, Parser, Query

lang = Language(tree_sitter_python.language())
parser = Parser(lang)

code = b'''
from fastapi import Depends
@verify_token
@app.get("/users")
def get_users(db = Depends(get_db_session)):
    pass
'''
tree = parser.parse(code)
print("PYTHON TREE:", str(tree.root_node))

py_query = Query(lang, '''
    (call function: (identifier) @name)
    (call function: (attribute attribute: (identifier) @name))
    (decorator (identifier) @name)
    (decorator (attribute attribute: (identifier) @name))
    (decorator (call function: (identifier) @name))
    (decorator (call function: (attribute attribute: (identifier) @name)))
    (call arguments: (argument_list (identifier) @name))
''')
from tree_sitter import QueryCursor
print("PY CAPTURES:", QueryCursor(py_query).captures(tree.root_node))

import tree_sitter_language_pack as tslp
dart_lang = tslp.get_language("dart")
dart_parser = Parser(dart_lang)

dart_code = b'''
class Processor {
  @override
  void process() {
    print('Processing');
    var data = fetchData();
    final user = User(name: 'Alice');
  }
}
'''
dart_tree = dart_parser.parse(dart_code)
print("DART TREE:", str(dart_tree.root_node))

dart_query = Query(dart_lang, '''
    (annotation name: (identifier) @name)
    ((identifier) @name . (selector))
''')
print("DART CAPTURES:", QueryCursor(dart_query).captures(dart_tree.root_node))

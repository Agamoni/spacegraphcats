import os.path
from . import graph_parser


class CAtlasReader(object):
    """
    Load the given catlas into 'edges', 'vertices', 'roots', 'levels',
    and 'catlas_id_to_domnode'.
    """
    def __init__(self, prefix, radius):
        self.prefix = prefix
        self.radius = radius

        self._load()

    def find_level0(self, node_id):
        """Take a node in the catlas and find all level 0 nodes beneath it.

        Return a set of domination graph node IDs.
        """

        x = set()

        beneath = self.edges.get(node_id, [])
        if beneath:
            # recurse!
            for y in beneath:
                x.update(self.find_level0(y))
            return x
        else:
            # only thing there should be nothing beneath are the leaves...
            assert self.levels[node_id] == 0
            # convert leaves into the original domination graph IDs.
            return set([self.catlas_id_to_domnode[node_id]])

    def _load(self):
        basename = os.path.basename(self.prefix)
        catlas_gxt = '%s.catlas.%d.gxt' % (basename, self.radius)
        catlas_gxt = os.path.join(self.prefix, catlas_gxt)
        self.catlas_gxt = catlas_gxt

        assignment_vxt = '%s.assignment.%d.vxt' % (basename, self.radius)
        assignment_vxt = os.path.join(self.prefix, assignment_vxt)
        self.assignment_vxt = assignment_vxt

        catlas_mxt = '%s.catlas.%d.mxt' % (basename, self.radius)
        catlas_mxt = os.path.join(self.prefix, catlas_mxt)
        self.catlas_mxt = catlas_mxt

        original_graph = '%s.gxt' % (basename)
        original_graph = os.path.join(self.prefix, original_graph)
        self.original_graph = original_graph

        edges = {}
        vertices = {}
        roots = []
        levels = {}
        catlas_id_to_domnode = {}

        def add_edge(a, b, *extra):
            x = edges.get(a, [])
            x.append(b)
            edges[a] = x

        def add_vertex(node_id, size, names, vals):
            assert names[0] == 'vertex'
            assert names[1] == 'level'
            vertex, level = vals
            if vertex == 'root':
                roots.append(node_id)

            level = int(level)
            levels[node_id] = level

            try:
                v = int(vertex)
                assert node_id not in catlas_id_to_domnode
                catlas_id_to_domnode[node_id] = v
            except ValueError:
                # catlas node not in domgraph
                pass

        graph_parser.parse(open(catlas_gxt), add_vertex, add_edge)

        self.edges = edges
        self.vertices = vertices
        self.roots = roots
        self.levels = levels
        self.catlas_id_to_domnode = catlas_id_to_domnode
    
    def find_matching_nodes_best_match(self, query_mh, mxt_dict):
        best_match = -1
        best_match_node = None
        best_mh = None
        for catlas_node, subject_mh in mxt_dict.items():
            match = query_mh.compare(subject_mh)

            if match > best_match:
                best_match = match
                best_match_node = catlas_node
                best_mh = subject_mh

        print('best match: similarity %.3f, catlas node %d' % \
                  (best_match, best_match_node))

        return [best_match_node]


    def find_matching_nodes_search_level(self, query_mh, mxt_dict, level=0):
        all_nodes = []

        for catlas_node, subject_mh in mxt_dict.items():
            if self.levels[catlas_node] != level:
                continue

            match1 = query_mh.compare(subject_mh)
            match2 = subject_mh.compare(query_mh)

            if match1 >= 0.05 or match2 >= 0.05:
                print('match!', match1, match2)
                all_nodes.append(catlas_node)

        return all_nodes


    def find_matching_nodes_gather_mins(self, query_mh, mxt_dict, level=3):
        """
        Find matching nodes at specified level;
        eliminate those that are entirely redundant, by examining contents
        of minhash.
        """
        all_nodes = []
        matches = []

        for catlas_node, subject_mh in mxt_dict.items():
            if self.levels[catlas_node] != level:
                continue

            match1 = query_mh.compare(subject_mh)

            if match1 >= 0.05:
                print('match!', match1)
                matches.append((match1, catlas_node, subject_mh))

        print('found %d matches; sorting and deredundanticizing' % len(matches))
        matches.sort(reverse=True)

        keep = []
        query_mins = set(query_mh.get_mins())
        sofar = set()
        for (score, node_id, mh) in matches:
            thismins = set(mh.get_mins())
            if (thismins - sofar).intersection(query_mins):
                keep.append((score, node_id, mh))
                sofar.update(thismins)

        print('had %d, now have %d' % (len(matches), len(keep)))

        all_nodes = [ x[1] for x in keep ]

        return all_nodes


    def find_matching_nodes_gather_mins2(self, query_mh, mxt_dict, level=3):
        """
        Find matching nodes at specified level;
        descend one level, gather nodes;
        eliminate those that are entirely redundant, by examining contents
        of minhash.
        """
        all_nodes = []
        matches = []

        for catlas_node, subject_mh in mxt_dict.items():
            if self.levels[catlas_node] != level:
                continue

            match1 = query_mh.compare(subject_mh)

            if match1 >= 0.05:
                print('match!', match1)
                matches.append((match1, catlas_node, subject_mh))

        print('found %d matches; sorting and deredundanticizing' % len(matches))
        matches.sort(reverse=True)

        # extract nodes beneath these nodes
        subnodes = set()
        for (score, node_id, mh) in matches:
            subnodes.update(self.edges.get(node_id, []))

        # get the non-redundant subnodes
        keep = []
        query_mins = set(query_mh.get_mins())
        sofar = set()
        for subnode in subnodes:
            mh = mxt_dict[subnode]
            thismins = set(mh.get_mins())
            if (thismins - sofar).intersection(query_mins):
                keep.append(subnode)
                sofar.update(thismins)

        print('had %d, now have %d' % (len(matches), len(keep)))

        return keep

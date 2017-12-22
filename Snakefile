# pull values in from config file:
catlas_base=config['catlas_base']
input_sequences=config['input_sequences']
ksize=config['ksize']
radius=config['radius']
searchseeds=config.get('searchseeds', 43)

catlas_dir = '{}_k{}_r{}'.format(catlas_base, ksize, radius)

# internal definitions for convenience:
python=sys.executable  # define as the version of Python running snakemake

###############################################################################
## some utility functions.

# rewrite the datasets into bcalm format
def write_bcalm_in(datasets):
    x = []
    for d in datasets:
        x.append('-in {}'.format(d))
    return " ".join(x)


def parse_seeds(seeds_str):
    seeds = []
    seeds_str = seeds_str.split(',')
    for seed in seeds_str:
        if '-' in seed:
            (start, end) = seed.split('-')
            for s in range(int(start), int(end) + 1):
                seeds.append(s)
        else:
            seeds.append(int(seed))

    return seeds


###############################################################################

## now, build some variables...

BCALM_INPUT=write_bcalm_in(input_sequences)
SEEDS=parse_seeds(config['searchseeds'])

### rules!

# build catlas & minhashes needed for search
rule all:
    input:
        expand("{catlas_dir}/catlas.csv", catlas_dir=catlas_dir),
        expand("{catlas_dir}/minhashes.db.k{ksize}.s1000.abund0.seed{seed}", catlas_dir=catlas_dir, seed=SEEDS, ksize=ksize)

# build cDBG using bcalm
rule bcalm_cdbg:
     input:
        input_sequences
     output:
        "bcalm.{catlas_dir}.k{ksize}.unitigs.fa"
     shell:
        # @CTB here we run into the problem that bcalm wants
        # '-in file1 -in file2', so I am using 'params' and 
        "bcalm {BCALM_INPUT} -out bcalm.{wildcards.catlas_dir}.k{wildcards.ksize} -kmer-size {wildcards.ksize} -abundance-min 1 >& {output}.log.txt"

# build catlas input from bcalm output by reformatting
rule bcalm_catlas_input:
     input:
        expand("bcalm.{{catlas_dir}}.k{ksize}.unitigs.fa", ksize=ksize)
     output:
        "{catlas_dir}/cdbg.gxt",
        "{catlas_dir}/contigs.fa.gz"
     shell:
        "{python} -m search.bcalm_to_gxt {input} {catlas_dir}/cdbg.gxt {catlas_dir}/contigs.fa.gz"


# build catlas!
rule build_catlas:
     input:
        "{catlas_dir}/cdbg.gxt",
        "{catlas_dir}/contigs.fa.gz",
     output:
        "{catlas_dir}/first_doms.txt",
        "{catlas_dir}/catlas.csv"
     shell:
        "{python} -m spacegraphcats.catlas {catlas_dir} {radius}"

# build minhash databases
rule minhash_db:
     input:
        "{catlas_dir}/cdbg.gxt",
        "{catlas_dir}/contigs.fa.gz",
        "{catlas_dir}/first_doms.txt",
     output:
        "{catlas_dir}/minhashes.db.k{ksize}.s1000.abund0.seed{seed}"
     shell:
        "{python} -m search.make_catlas_minhashes -k {wildcards.ksize} --seed={wildcards.seed} --scaled=1000 {catlas_dir}"

### Search rules.

def make_query_base(catlas_dir, searchfiles):
    x = []
    for filename in searchfiles:
        x.append("{}_search/{}.contigs.sig".format(catlas_dir, os.path.basename(filename)))
    return x

# do a quick search!
rule searchquick:
    input:
        config['searchquick'],
        "{params.catlas_dir}/first_doms.txt"
        "{params.catlas_dir}/catlas.csv",
        expand("{{params.catlas_dir}}/minhashes.db.k{{params.ksize}}.s1000.abund0.seed{seed}", seed=SEEDS)
    output:
        "{params.catlas_dir}_search/results.csv",
        make_query_base(catlas_dir, config['searchquick'])
    shell:
        "{python} -m search.extract_nodes_by_query {catlas_dir} {catlas_dir}_search --query {config[searchquick]} --seed={searchseeds} -k {ksize}"


# do a full search!
rule search:
    input:
        config['search'],
        expand("{catlas_dir}/first_doms.txt", catlas_dir=catlas_dir),
        expand("{catlas_dir}/catlas.csv", catlas_dir=catlas_dir),
        expand("{catlas_dir}/minhashes.db.k{ksize}.s1000.abund0.seed{seed}", catlas_dir=catlas_dir, seed=SEEDS, ksize=ksize),
    output:
        expand("{catlas_dir}_search/results.csv", catlas_dir=catlas_dir),
        make_query_base(catlas_dir, config['search']),
    shell:
        "{python} -m search.extract_nodes_by_query {catlas_dir} {catlas_dir}_search --query {config[search]} --seed={searchseeds} -k {ksize}"
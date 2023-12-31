
import os
import numpy as np
import pandas as pd
import seaborn as sns
import matplotlib.patches as patches
import matplotlib.pyplot as plt
from itertools import combinations
from sklearn.cluster import KMeans



class Analysis:
    def __init__(self, protein_state,):
        
        if not isinstance(protein_state, list):
            self.protein_state = [protein_state]
        else:
            self.protein_state = protein_state

        initial_sliding_windows = self._get_initial_sliding_windows()
        self.__minimize_overlap_by_single_res(initial_sliding_windows)
        self.__minimize_overlap_by_adjacent_windows(initial_sliding_windows)
        self.maximum_resolution_limits = self.__find_continuous_blocks(initial_sliding_windows)


    
    def find_mini_overlap(self, peps_covering,):

        '''
        find the mini overlap give peps covering a residue
        '''

        combinations_list = list(combinations(peps_covering, 2))

        overlaps = []

        for comb in combinations_list:
            #get the overlap
            overlap_start = max(comb[0].start, comb[1].start)
            overlap_end = min(comb[0].end, comb[1].end)
            overlap = (overlap_start, overlap_end)
            #if res_i_start in range(overlap_start, overlap_end):
            overlaps.append(overlap)

        min_overlap = min(overlaps, key=lambda x: x[1]-x[0])

        return min_overlap
    

    def _get_initial_sliding_windows(self):
        
        '''
        get the initial sliding windows for each residue
        input: protein_state
        '''

        all_peptides = [pep for state in self.protein_state for pep in state.peptides ]

        min_covering_pep_dict = {}
        for i in range(len(self.protein_state[0].hdxms_data.protein_sequence)):

            #! all_peptides must contain substracted peptides
            peps_covering = [pep for pep in all_peptides if pep.start <= i+1 <= pep.end]
            
            if len(peps_covering) == 0 or self.protein_state[0].hdxms_data.protein_sequence[i] == 'P':
                continue
            elif len(peps_covering) == 1:
                min_covering_pep = (peps_covering[0].start, peps_covering[0].end)
            else:
                min_covering_pep = self.find_mini_overlap(peps_covering)
            
            min_covering_pep_dict[i+1] = min_covering_pep
            #print(i+1, min_covering_pep)

        return min_covering_pep_dict
    


    def __minimize_overlap_by_single_res(self, my_dict):
        changes_made = True

        while changes_made:
            changes_made = False
            single_res = [k for k, v in my_dict.items() if v[0] == v[1]]

            for key, value in list(my_dict.items()):
                v0, v1 = value
                original_value = (v0, v1)

                if (v0 in single_res or v1 in single_res) and v0 != v1:
                    if v0 in single_res:
                        v0 += 1
                    if v1 in single_res:
                        v1 -= 1

                    if v0 > v1:
                        v0, v1 = v1, v0

                    my_dict[key] = (v0, v1)

                if my_dict[key] != original_value:
                    changes_made = True


    def __minimize_overlap_by_adjacent_windows(self, my_dict):
        changes_made = True

        while changes_made:
            changes_made = False
            sorted_keys = sorted(my_dict.keys())

            # Adjust overlapping ranges
            for i in range(len(sorted_keys)):
                key = sorted_keys[i]
                v0, v1 = my_dict[key]

                # Check and adjust overlaps with the next tuple
                if i < len(sorted_keys) - 1:
                    next_key = sorted_keys[i + 1]
                    next_v0, next_v1 = my_dict[next_key]
                    if v1 >= next_v0:
                        # Adjust the range of the next tuple to remove overlap
                        new_v0 = v1 + 1
                        if new_v0 <= next_v1:
                            my_dict[next_key] = (new_v0, next_v1)
                            changes_made = True

                # Check and adjust overlaps with the previous tuple
                if i > 0:
                    prev_key = sorted_keys[i - 1]
                    prev_v0, prev_v1 = my_dict[prev_key]
                    if prev_v1 >= v0:
                        # Adjust the range of the current tuple to remove overlap
                        new_v1 = v0 - 1
                        if new_v1 >= prev_v0:
                            my_dict[prev_key] = (prev_v0, new_v1)
                            changes_made = True

        return my_dict




    def __find_continuous_blocks(self, input_dict):
        # Sort the keys
        sorted_keys = sorted(input_dict.keys())

        # Initialize the first block
        blocks = []
        current_block = [sorted_keys[0]]
        current_range = input_dict[sorted_keys[0]]

        # Function to check if two ranges overlap
        def ranges_overlap(range1, range2):
            return range1[1] >= range2[0] and range2[1] >= range1[0]

        # Iterate through the sorted keys
        for key in sorted_keys[1:]:
            key_range = input_dict[key]

            # Check if the current key overlaps with the current block's range
            if ranges_overlap(current_range, key_range):
                current_block.append(key)
                # Update the block's range to the overlapping portion
                current_range = (max(current_range[0], key_range[0]), min(current_range[1], key_range[1]))
            else:
                # Save the current block and start a new one
                blocks.append((current_block, current_range))
                current_block = [key]
                current_range = key_range

        # Add the last block
        blocks.append((current_block, current_range))

        # make it a dictionary
        blocks = {res: block[1] for block in blocks for res in block[0]}


        return blocks


    def load_bayesian_hdx_oupt(self, bayesian_hdx_data_file):
        pof = Bayesian_hdx_ParseOutputFile(bayesian_hdx_data_file)
        self.bayesian_hdx_df = pof.get_best_scoring_models_pf_df(N=50)
        
        
    

    def clustering_results(self):
        
        results = Results(self)
        
        for k,v in self.maximum_resolution_limits.items():
            try:
                mini_pep = results.get_mini_pep(v[0], v[1])
            except:
                mini_pep = MiniPep(v[0], v[1])
                results.add_mini_pep(mini_pep)
                
            #print(k,v, clustering_a_mini_pep(k, v[0], v[1]))
            res = results.get_residue_by_resid(k)
            mini_pep.add_residue(res)
            mini_pep.set_clustering_results(self._clustering_a_mini_pep(k, v[0], v[1]))
            
        self.results_obj = results


    def _clustering_a_mini_pep(self, k, v0, v1):

        
        # v0 and v1 are 1-based
        # Apply remove_outliers to each column and collect results
        cleaned_data = [remove_outliers(self.bayesian_hdx_df[col]) for col in self.bayesian_hdx_df.iloc[:,v0-1:v1].columns] 
        
        
        initial_centers = np.array([np.mean(col) for col in cleaned_data if col.size !=0]).reshape(-1, 1)  
        num_clusters = initial_centers.shape[0]
        
        if num_clusters == 0:
            return np.array([np.nan])
        
        pool_values = np.concatenate(cleaned_data).flatten()
        pool_values = pool_values[~np.isnan(pool_values)]
        
        if len(pool_values) != 0:
            k_cluster = KMeans(n_clusters=num_clusters, random_state=0, init=initial_centers, n_init='auto').fit(pool_values.reshape(-1, 1))    
            return np.sort(k_cluster.cluster_centers_.flatten())

    
        

    def plot_pf_bar(self, ax=None, label=None, resolution_indicator_pos=15):
        #mini_peps_index = sorted(list(set([(v[0]-1, v[1]-1) for k, v in self.maximum_resolution_limits.items()])))
        # xx = self.bayesian_hdx_df.mean().values

        # for mini_pep in mini_peps_index:
        #     indexes = [i for i in range(mini_pep[0], mini_pep[1]+1) if np.isnan(self.bayesian_hdx_df.mean()).iloc[i] == False] 
        #     xx[indexes] = sorted(xx[indexes])

        self.clustering_results()
        
        xx = np.array([res.resid for res in self.results_obj.residues if res.is_nan() == False])
        yy = np.concatenate([mini_pep.clustering_results for mini_pep in self.results_obj.mini_peps])

        # padding all the residues
        padded_xx = np.arange(1, self.results_obj.n_residues+1)
        padded_yy = np.zeros(self.results_obj.n_residues)

        for i in range(len(xx)):
            padded_yy[xx[i]-1] = yy[i]
        

        if ax is None:
            fig, ax = plt.subplots(figsize=(20, 5))
        
        sns.barplot(x=padded_xx, y=padded_yy, ax=ax, label=label, alpha=0.5)
        #sns.barplot(x=range(1, len(xx)+1), y=xx, alpha=0.5, label='bayesian_hdx', ax=ax)
        
        for mini_pep in self.results_obj.mini_peps:
            width = mini_pep.end - mini_pep.start
            height = 0.5  # Height can be adjusted based on visual preference
            #rect = patches.Rectangle((mini_pep.start-1, ax.get_ylim()[1]-0.7), width, height, linewidth=1, edgecolor='k', facecolor='lightgrey')
            rect = patches.Rectangle((mini_pep.start-1, resolution_indicator_pos), width, height, linewidth=1, edgecolor='k', facecolor='lightgrey')
            ax.add_patch(rect)

        #plt.legend(loc='upper left')
        plt.tight_layout()
        plt.xlabel('Resid')
        plt.ylabel('logP')
        plt.xticks(rotation=90);
        ax.set_ylim(0, 17)
        
        
        #add the coverage heatmap
        coverage = self.calculate_coverages()
        for i in range(len(coverage)):
            color_intensity = coverage[i] / 20 # coverage.max()  # Normalizing the data for color intensity
            rect = patches.Rectangle((i, 16), 1, height, color=plt.cm.Blues(color_intensity))
            ax.add_patch(rect)
            


        return ax
    
    #print(mini_pep[0]+1, mini_pep[1]+1)

    def calculate_coverages(self):
        all_peptides = [pep for state in self.protein_state for pep in state.peptides ]
        max_end = max(pep.end for pep in all_peptides)
        coverage = np.zeros(max_end + 1)
        for pep in all_peptides:
            coverage[pep.start:pep.end + 1] += 1
        return coverage[1:]


class Results(object):
    
    def __init__(self, analysis_object: Analysis):
        
        self.analysis_object = analysis_object
        
        self.protein_name = analysis_object.protein_state[0].hdxms_data.protein_name
        self.protein_sequence = analysis_object.protein_state[0].hdxms_data.protein_sequence
        self.protein_state = analysis_object.protein_state
        self.add_residues()
        self.mini_peps = []
    
    def add_residues(self):
        self.residues = []
        for i in range(len(self.protein_sequence)):
            res = Residue(i+1, i, self.protein_sequence[i])
            res.set_resluts_obj(self)
            self.residues.append(res)
            
    @property
    def n_residues(self):
        return len(self.residues)
            
    def get_residue_by_resid(self, resid):
        for res in self.residues:
            if res.resid == resid:
                return res
        raise Exception('residue not found')
    
    def get_residue_by_resindex(self, resindex):
        return self.get_residue_by_resid(resindex+1)
    
    
    def add_mini_pep(self, mini_pep):
        if mini_pep in self.mini_peps:
            print('mini_pep already exists')
        self.mini_peps.append(mini_pep)
    
     
    def get_mini_pep(self, start, end):
        for mini_pep in self.mini_peps:
            if mini_pep.start == start and mini_pep.end == end:
                return mini_pep
        raise Exception('mini_pep not found')

       
class Residue(object):
    def __init__(self, resid, resindex, resname):
        self.resid = resid # 1-based
        self.resindex = resindex # 0-based
        self.resname = resname # one letter code
        
        
    def set_resluts_obj(self, resluts_obj):
        self.resluts_obj = resluts_obj

    def set_mini_pep(self, mini_pep):
        self.mini_pep = mini_pep
        
    def is_nan(self):
        return self.resluts_obj.analysis_object.bayesian_hdx_df.mean().isna()[self.resindex]

        
class MiniPep(object):
    '''
    maximum_resolution_limits: {resid: [v0, v1]}
    can be a single residue or a range of residues
    '''
    def __init__(self, start, end):
        self.start = start
        self.end = end
        self.residues = []

    def set_clustering_results(self, clustering_results):
        self.clustering_results = clustering_results
        
    def if_single_residue(self):
        return self.start == self.end
    
    def add_residue(self, residue):
        if residue in self.residues:
            raise Exception('residue already exists')
        self.residues.append(residue)
        residue.set_mini_pep(self)
        


class Bayesian_hdx_ParseOutputFile(object):
    '''
    !!! Forked from salilab/bayesian_hdx
    
    An object that stores all of the information from an hxio.Output file.
    Also can be used as a general tool for analyzing sets of data.

    To create a copy of this object, do >new_pof = deepcopy(pof) to retain all
    of the header information and then clear the models

    '''
    def __init__(self, output_file):
        self.output_file = output_file
        self.datafiles = []
        self.datasets=[]
        self.sectors = []
        self.models=[]
        self.pf_grids = {}
        self.observed_residues = []
        self.parse_header()
        self.path = os.path.dirname(os.path.realpath(output_file))

    def get_sequence(self):
        '''
        Return the macromolecule sequence from the output file
        '''
        return self.get_datasets()[0].sequence


    def parse_header(self):
        '''
        Function that parses the header of output files.
        Stores the logk grid, along with other experimental information
        '''
        f = open(self.output_file, "r")
        for line in f.readlines():
            
            # > means model data (so header is over.)
            if line[0]==">":
                break
            
            # #-symbol means datasets
            elif line[0:2]=="# ":
                self.datafiles.append( (line[2:].split("|")[0].strip(), float(line[2:].split("|")[2].strip())) )
            
            # @-symbol means sectors
            elif line[0:2]=="@ ":
                for s_string in line[2:].strip().split("|"):
                    sector = []
                    for r in s_string.strip().split(" "):
                        if r != "":
                            sector.append(int(r))
                            self.observed_residues.append(int(r))
                    self.sectors.append(sector)

            elif line[0:2]=="$ ":
                if line[2:].split("|")[0].strip() != "Residue_number":
                    res = int(line[2:].split("|")[0].strip())
                    grid = []
                    for pf in line[2:].split("|")[1].strip().split(" "):

                        grid.append(float(pf))
                    self.pf_grids[res] = grid

            elif line.split(":")[0].strip() == "grid_size":
                self.grid_size = int(line.split(":")[1].strip())

            elif line.split(":")[0].strip() == "State":
                self.state_name = line.split(":")[1].strip()

            elif line.split(":")[0].strip() == "Molecule_Name":
                self.molecule_name = line.split(":")[1].strip()
        f.close()

    def clear_models(self):
        self.models = []

    def cluster_models_kmeans(self, nmodels, nclust):
        # Uses kmeans to cluster models
        from sklearn.cluster import KMeans
        mods = [m[1] for m in self.get_best_scoring_models(N=nmodels)]
        models = np.array(mods)
        kmeans = KMeans(n_clusters=nclust).fit(models)

        for i in range(nclust):
            unique, counts = np.unique(kmeans.labels_, return_counts=True)
            print(nclust, " | ", i, dict(zip(unique, counts))[i] *1.0/nmodels)
        '''
        for c in range(len(kmeans.cluster_centers_)):
            for i in range(c,len(kmeans.cluster_centers_)):
                print(i, c, np.linalg.norm(kmeans.cluster_centers_[c]-kmeans.cluster_centers_[i]))
        '''

    def get_datasets(self):
        if len(self.datasets) == 0:
            self.generate_datasets()
        return self.datasets

    def generate_datasets(self):
        self.datasets=[]
        for f in self.datafiles:
            #print(self.path, f)
            self.datasets.append(hxio.import_json(self.path+f[0]))

    def get_models(self, return_pf=False):
        # returns all models stored in the POF (not the data file)
        if return_pf:
            return self.models_to_protection_factors(self.models)
        else:
            return self.models

    def get_all_models(self, return_pf=False):
        f = open(self.output_file, "r")
        models = []
        # Cycle over all lines
        for line in f.readlines():       
            if line[0]==">":
                score = float(line.split("|")[1].strip())

                model_string = line[1:].split("|")[0].strip()
                model_list = []
                for m in model_string.split(" "):
                    model_list.append(int(m))
                if return_pf:
                    ml1 = model_list
                    model_list = self.models_to_protection_factors(model_list)
                models.append((score, model_list)) 

        self.models = models

        return models

    def get_scores(self):
        try:
            models = self.models
        except:
            models = self.get_all_models()

        scores = [mod[0] for mod in models]

        return np.sort(scores)


    def get_best_scoring_models(self, N="all", sigmas=False, return_pf=False, sort_sectors=False):
        ''' Get the N best scoring models from the output file
        Returns a list of tuples of best_scoring_models 
            [(score, [model])]
        and (if sigmas=True)
        a grid of the timepoint sigma values.
        '''
        # Model entries are marked with a > as the first character

        if N=="all":
            N=100000000000

        f = open(self.output_file, "r")
        best_scoring_models = []
        # Cycle over all lines
        for line in f.readlines():
            if line[0]==">":
                score = float(line.split("|")[1].strip())

                # if the score is better than the last best score
                if len(best_scoring_models) < N or score < best_scoring_models[-1][0]:
                    if len(best_scoring_models) >= N:
                        del best_scoring_models[-1]
                        #print(score, best_scoring_models[-1])
                    model_string = line[1:].split("|")[0].strip()
                    model_list = []
                    for m in model_string.split(" "):
                        model_list.append(int(m))
                    if sort_sectors:
                        model_list = self.sort_model_by_sector(model_list)
                    if return_pf:
                        ml1 = model_list
                        model_list = self.models_to_protection_factors(model_list)
                        #print(score, model_list, ml1)
                    best_scoring_models.append((score, model_list))
                    best_scoring_models = sorted(best_scoring_models, key=lambda x: x[0])

        self.best_scoring_models = best_scoring_models

        return best_scoring_models

    def models_to_protection_factors(self, models):
        # Input a list of list of integers.  
        # CHECK THAT THE MODEL SIZE IS CORRECT!

        if type(models[0]) != list:
            models = [models]

        protection_factor_models = []

        for m in models:
            pf_model = []
            for res in range(len(m)):
                if res + 1 in self.observed_residues:
                    #print("RES", res+1, m[res], self.pf_grids[res+1][m[res]-1])
                    pf_model.append(float(self.pf_grids[res+1][m[res]-1]))
                else:
                    pf_model.append(np.nan)
            protection_factor_models.append(pf_model)
            #print("MOD:", m[38:45])
            #print("PF:",pf_model[38:45])
        return protection_factor_models

    def get_sectors(self):
        # returns the list of sectors
        return self.sectors

    def sort_model_by_sector(self, model):
        # Given an input of a single model (as a list of integers), and a list
        # of sectors (as a list of list of residue numbers), return the model
        # with the integers in each sector sorted in increasing order. 

        # check that the model and total length of the sectors is the same:
        s_len = 0
        s_len = sum([len(s) for s in self.sectors])

        out_model = np.zeros(len(model))
        # Loop over all sectors
        for s in self.sectors:
            if len(s) == 0:
                continue

            sec_model = model[s[0]-1:s[-1]]
            sort_model = np.sort(sec_model) #sort indexes in increasing order

            idx_zero = [index for index, v in enumerate(sec_model) if v == 0]
            idx_nonzero = [index for index, v in enumerate(sec_model) if v != 0]
            offset=0
            for i in range(len(s)):
                if i in idx_zero:
                    out_model[i] = 0
                    offset += 1
                else:
                    out_model[i+offset] = sort_model[i + len(idx_zero)-offset]
                out_model[idx_nonzero[i] - 1 + s[0]] = sort_model[i + len(idx_zero)]
        return out_model.astype(int)

    def calculate_random_sample_convergence(self, replicates=100, pct_values=10):
        """ 
            For each sample of good scoring models (self.get_best_scoring_models)

            Get a list of top scores from each.

            Store the results as a list of two lists (one for each sample)
            with each sample list containing a tuple :: (pct, avg, stdev)
        """
        delpct = 1.0 / pct_values

        pct_grid = np.arange(delpct, 1.0, delpct)

        convergence_tuples = []

        scores = [g[0] for g in self.get_best_scoring_models()]

        pct_tuples = []

        for p in pct_grid:
            min_scores = []
            # For each percent value, take N samples and report avg/std of minimum values
            for r in range(replicates):
                subset = self._random_subset(scores, p)
                min_scores.append(min(subset))
            array = np.array(min_scores)

            pct_tuples.append((p, np.average(array), np.std(array)))

            print((p, np.average(array), np.std(array)), len(subset))

        convergence_tuples.append(pct_tuples)

        #print(convergence_tuples)
        del scores


    def _random_subset(self, models, pct):
        """
            Generate a random subset of pct percent of the given list of things
            @param models - python list of model dictionaries (really, could be anything)
            @param pct - the fraction of samples to return
        """
        import random
        if pct > 1.0:
            print("WARNING: percent value should be between 0 and 1.0. Diving by 100")
            pct = pct/100.0
        if pct > 1.0 or pct <= 0:
            print("WARNING: percent value is outside of bounds")

        num_samples = int(len(models) * pct)
        rand_smpl = [models[i] for i in random.sample(range(len(models)), num_samples)]
        #print(num_samples, len(models), len(rand_smpl), models)
        return rand_smpl
    
    
    def get_best_scoring_models_pf_df(self,  N=200):
        
        self.get_best_scoring_models(N=N, return_pf=True, sort_sectors=True)
        
        pfs = []      
        for i in self.best_scoring_models:
            # Append just the model itself. 
            pfs.append(np.array(i[1][0]))
            
        df_pfs = pd.DataFrame(pfs)
        
        return df_pfs
    
    

# some helper functions

def remove_outliers(data):

    # Convert input to numpy array in case it's a list or other array-like object
    data = np.array(data)
    
    # Calculate Q1, Q3, and IQR
    Q1 = np.percentile(data, 25)
    Q3 = np.percentile(data, 75)
    IQR = Q3 - Q1

    # Identify outliers
    lower_bound = Q1 - (1.5 * IQR)
    upper_bound = Q3 + (1.5 * IQR)

    # Remove outliers
    return data[(data >= lower_bound) & (data <= upper_bound)]
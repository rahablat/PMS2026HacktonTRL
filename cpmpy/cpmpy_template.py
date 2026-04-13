import cpmpy as cp
import numpy as np
import json

from pms.box import Box
from pms.box_var import BoxVar, BlockvizEncoder
from cpmpy.solvers.ortools import OrtSolutionPrinter

import sys
from contextlib import contextmanager
import os
from pathlib import Path





# ===============================
# Utils functions
# ===============================

@contextmanager
def redirect_ortools_logs(filepath):
    """
    Redirect ORTools logs to a file.
    """
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    f = open(filepath, "w")
    sys.stdout = f
    sys.stderr = f

    try:
        yield
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        f.close()



def convert_solution_to_json(scene: dict) -> None:
    """
    Convert a solution to a JSON suitable for blockviz
    """
    json_line = json.dumps(
        scene,
        cls=BlockvizEncoder
    )
    return json_line


# ===============================
# CPMpyModel class
# ===============================



class CPMpyModel:
    def __init__(self):
        self.model = cp.Model()   # CPMpy model
        self.list_boxes = []
        self.list_boxes_var = []

    def open_data(self, path: str) -> list[Box]:
        """
        Create a list of Box object from a data instance
        """
        with open(path, "r") as f:
            list_boxes = Box.read_csv(f)
        self.list_boxes = list_boxes
        return list_boxes
    
    def create_variables(self, max_dimension : int = 5000) -> list[BoxVar]:
        """
        Create necessary variables for each box, and return a list of BoxVar objects.
        """
        list_boxes_var = []
        for box in self.list_boxes:
            position = cp.intvar(0, max_dimension, shape = 3, name = f"{box.name}_position")
            color = np.random.randint(0, 255, size = 3)
            box_var = BoxVar(box, position, color)
            list_boxes_var.append(box_var)
        self.list_boxes_var = list_boxes_var
        return list_boxes_var
    

    def create_objective(self):
        """
        Create the objective function
        """
        max_x = cp.max(box_var.position[0] + box_var.box.size[0] for box_var in self.list_boxes_var)
        max_y = cp.max(box_var.position[1] + box_var.box.size[1] for box_var in self.list_boxes_var)
        max_z = cp.max(box_var.position[2] + box_var.box.size[2] for box_var in self.list_boxes_var)
        self.model.minimize(cp.sum([max_x, max_y, max_z]))


    def solve(self, path, ortools_logs = False, ortools_logs_path = "ortools_logs.txt", **kwargs):
        """
        Solve the CPMpy model, and print solutions in real-time in a suitable format for blockviz.

        Parameters
        -----------------
        path : str
            Path to save the final solution obtained
        ortools_logs : bool
            If True, ORTools logs are saved in a file.
        ortools_logs_path : str
            Path to save ORTools logs.
        kwargs : dict
            Additional arguments for the ORTools solver.
        """
        scene_list = []

        def myprint():
            time = cb.WallTime()
            sol_nbr = cb.solution_count()
            obj_val = cb.ObjectiveValue()
            scene = {"boxes": [],
                    "text": "Solution {}: objective value = {}, time = {}s".format(sol_nbr, obj_val, time)}
            for box_var in self.list_boxes_var:
                scene["boxes"].append({"position" : box_var.position.value().tolist(),
                                        "size" : box_var.box.size,
                                        "color" : box_var.color.tolist()})
            scene_list.append(scene)
            print(convert_solution_to_json(scene), file=sys.__stdout__)

        s = cp.SolverLookup.get('ortools', self.model)
        cb = OrtSolutionPrinter(s, display = myprint)

        if ortools_logs:
            with redirect_ortools_logs(ortools_logs_path):
                s.solve(enumerate_all_solutions=False, solution_callback=cb, log_search_progress=True, log_to_stdout = False, **kwargs)
        else:
            s.solve(enumerate_all_solutions=False, solution_callback=cb, log_search_progress=False, **kwargs)

        # Save the obtained solution :
        scene = {"boxes": [],
                    "text": "Solution"}
        for box_var in self.list_boxes_var:
            scene["boxes"].append({"position" : box_var.position.value().tolist(),
                                    "size" : box_var.box.size,
                                    "color" : box_var.color.tolist()})
            
        with open(path, "w") as f:
            f.write(convert_solution_to_json(scene))

        
    


# ===============================
# Main code
# ===============================


def solve_all():
    for name in ["random", "hetero", "homo"] :
        for nbr in ["0005", "0010", "0020", "0050", "0100"]:#, "0200", "0500"] :
            data_path = f"dataset/{name}_{nbr}.csv"
            solution_path = f"solutions/{name}_{nbr}.json"
            main(data_path, solution_path)




def main(data_path, solution_path):
    # Initialize CPMpy model, open data and create variables
    mymodel = CPMpyModel()
    mymodel.open_data(path = data_path)
    list_boxes_var = mymodel.create_variables()

    # You can add here your constraints to the model CPMpy, which you can access with mymodel.model, using variables saved in list_boxes_var.

    # for i in range(len(list_boxes_var)-1):
    #     mymodel.model.add(list_boxes_var[i+1].position[0] >= list_boxes_var[i].position[0] + list_boxes_var[i].box.length)
    #     mymodel.model.add(list_boxes_var[i+1].position[1] >= list_boxes_var[i].position[1] + list_boxes_var[i].box.width)
    #     mymodel.model.add(list_boxes_var[i+1].position[2] >= list_boxes_var[i].position[2] + list_boxes_var[i].box.height)

    # mymodel.model.add( cp.NoOverlap( [box.position[0] for box in list_boxes_var],  [box.box.length for box in list_boxes_var ]))  
    # mymodel.model.add( cp.NoOverlap( [box.position[1] for box in list_boxes_var],  [box.box.width for box in list_boxes_var ]))  
    # mymodel.model.add( cp.NoOverlap( [box.position[2] for box in list_boxes_var],  [box.box.height for box in list_boxes_var ]))  

    box_i_before_j = []
    for _ in range(len(list_boxes_var)):
        box_i_before_j.append([])
        for _ in range(len(list_boxes_var)):
            box_i_before_j[-1].append( cp.intvar(0,1,shape=3))
    for i in range(len(list_boxes_var)):
        for j in range(len(list_boxes_var)):
            if i != j :
                mymodel.model.add( box_i_before_j[i][j][0] + box_i_before_j[i][j][1] + box_i_before_j[i][j][2] + box_i_before_j[j][i][0] + box_i_before_j[j][i][1] + box_i_before_j[j][i][2] >= 1 )
                mymodel.model.add( list_boxes_var[j].position[0] + (1-box_i_before_j[i][j][0])*5000 >= list_boxes_var[i].position[0] + list_boxes_var[i].box.length )
                mymodel.model.add( list_boxes_var[j].position[1] + (1-box_i_before_j[i][j][1])*5000  >= list_boxes_var[i].position[1] + list_boxes_var[i].box.width )
                mymodel.model.add( list_boxes_var[j].position[2] + (1-box_i_before_j[i][j][2])*5000 >= list_boxes_var[i].position[2] + list_boxes_var[i].box.height )


    
    # Create objective function and solve the model
    mymodel.create_objective()
    mymodel.solve(path = solution_path, time_limit = 60)   # You can add additional ORTools solver argument (like I've done with time_limit here)

    ## If you wish to save ORTools solver logs in a file, you can use the following arguments
    # mymodel.solve(path = solution_path, ortools_logs = True, ortools_logs_path = "ortools_logs.txt", time_limit = 60)
    print(data_path)
    print(solution_path)

if __name__ == "__main__":
    # # Paths
    # data_path = "dataset/hetero_0005.csv"
    # solution_path = "solution.json"
    #main(data_path, solution_path)
    solve_all()
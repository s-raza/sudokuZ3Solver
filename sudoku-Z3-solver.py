from z3 import Solver, Int, Or, Distinct, sat
from sudokuextract.extract import extract_sudoku, load_image, predictions_to_suduko_string
from sudokuextract.exceptions import *
import argparse

class Sudoku:

    def __init__(self, problem=None, constraints=None):

        self.blank_grid = """
        +-------+-------+-------+
        | 0 0 0 | 0 0 0 | 0 0 0 |
        | 0 0 0 | 0 0 0 | 0 0 0 |
        | 0 0 0 | 0 0 0 | 0 0 0 |
        +-------+-------+-------+
        | 0 0 0 | 0 0 0 | 0 0 0 |
        | 0 0 0 | 0 0 0 | 0 0 0 |
        | 0 0 0 | 0 0 0 | 0 0 0 |
        +-------+-------+-------+
        | 0 0 0 | 0 0 0 | 0 0 0 |
        | 0 0 0 | 0 0 0 | 0 0 0 |
        | 0 0 0 | 0 0 0 | 0 0 0 |
        +-------+-------+-------+
        """

        self.rows, self.cols = "ABCDEFGHI", "123456789"
        self.elements = self.cross(self.rows, self.cols)
        self.problem = self.parse_grid(problem)
        self.values = self.problem
        self.constraints = constraints

        self.unitlist = []
        self.unit_cols = [self.cross(self.rows, c) for c in self.cols]
        self.unit_rows = [self.cross(r, self.cols) for r in self.rows]
        self.unit_boxes = [self.cross(rs, cs) for rs in ["ABC", "DEF", "GHI"] for cs in ["123", "456", "789"]]

        self.unitlist = self.unit_cols+self.unit_rows+self.unit_boxes

        self.units = {e: [u for u in self.unitlist if e in u] for e in self.elements}

        self.solution = None

    def cross(self, A, B):

        return [(a + b) for a in A for b in B]

    def parse_grid(self, grid):
        """
        A1 A2 A3 | A4 A5 A6 | A7 A8 A9
        B1 B2 B3 | B4 B5 B6 | B7 B8 B9
        C1 C2 C3 | C4 C5 C6 | C7 C8 C9
        –––––––––+––––––––––+–––––––––
        D1 D2 D3 | D4 D5 D6 | D7 D8 D9
        E1 E2 E3 | E4 E5 E6 | E7 E8 E9
        F1 F2 F3 | F4 F5 F6 | F7 F8 F9
        –––––––––+––––––––––+–––––––––
        G1 G2 G3 | G4 G5 G6 | G7 G8 G9
        H1 H2 H3 | H4 H5 H6 | H7 H8 H9
        I1 I2 I3 | I4 I5 I6 | I7 I8 I9

        puzzle = 'A1A2A3A4...' and every element holds a value of '123456789.'
        where the dot represents an empty cell.
        """

        chars = [c for c in grid if c in "123456789" or c in '0.']

        if len(chars) != 81:
            raise Exception("got invalid puzzle format")

        values = {e: v for e,v in zip(self.elements, chars)}

        return values

    def get_constraints(self):
        
        retval = []
        
        for const in self.constraints.strip().split("\n"):
            parts = const.strip().split("=")

            squares = parts[0]
            constr_sum = int(parts[1])

            constr_squares = [square for square in squares.split("+")]

            retval.append((constr_squares,constr_sum))

        return retval

    def solve_z3(self):

        print("[+] {}".format("Sovling using Z3\n"))

        symbols = {e: Int(e) for e in self.elements}
        
        # first we build a solver with the general constraints for sudoku puzzles:
        s = Solver()

        # assure that every cell holds a value of [1,9]
        for symbol in symbols.values():
            s.add(Or([symbol == int(i) for i in self.cols]))

        # assure that every row covers every value:
        for row in "ABCDEFGHI":
            s.add(Distinct([symbols[row + col] for col in "123456789"]))

        # assure that every column covers every value:
        for col in "123456789":
            s.add(Distinct([symbols[row + col] for row in "ABCDEFGHI"]))

        # assure that every block covers every value:
        for i in range(3):
            for j in range(3):
                s.add(Distinct([symbols["ABCDEFGHI"[m + i * 3] + "123456789"[n + j * 3]] for m in range(3) for n in range(3)]))

        # adding sum constraints if provided
        if self.constraints is not None:
            print("[+] {}\n{}".format("Applying constraints", self.constraints))
            sum_constr = self.get_constraints()
            for c in sum_constr:
                expr = []

                for i in c[0]:
                    expr.append("symbols['" + i + "']")

                s.add(eval("+".join(expr)+"=="+str(c[1])))

        # now we put the assumptions of the given puzzle into the solver:
        for elem, value in self.values.items():
            if value in "123456789":
                s.add(symbols[elem] == value)

        if not s.check() == sat:
            raise Exception("Unsolvable")

        model = s.model()
        values = {e: model.evaluate(s).as_string() for e, s in symbols.items()}

        self.solution = values

    def get_oneline_grid(self, grid):

        return "[+] GRID:" + ''.join(grid[e] for e in self.elements) +"\n"

    def pretty_format(self, grid):

        return self.get_oneline_grid(grid) + self.get_grid(grid)

    def insert_grid_header(self, header, grid):

        grid.insert(0,header + " "*(len(grid[0])-len(header)))

        return grid


    def get_side_by_side(self, prob, sol):

        grid1_lines = self.get_grid(prob).split("\n")
        grid2_lines = self.get_grid(sol).split("\n")

        if len(grid1_lines) != len(grid2_lines):
            raise Exception("Grids have different dimensions")
        
        grid1_lines = self.insert_grid_header("PROBLEM", grid1_lines)
        grid2_lines = self.insert_grid_header("SOLUTION", grid2_lines)

        lines = ""

        for i in range(len(grid1_lines)):

            lines += grid1_lines[i] + " "*4 + grid2_lines[i] + "\n"

        return lines

    def get_grid(self, grid):
        lines = []

        for index_row, row in enumerate("ABCDEFGHI"):
            if index_row % 3 == 0:
                lines.append("+–––––––––+–––––––––+–––––––––+")

            line = ''
            for index_col, col in enumerate("123456789"):
                line += "{1} {0} ".format(grid[row + col], '|' if index_col % 3 == 0 else '')
            lines.append(line + '|')

        lines.append("+–––––––––+–––––––––+–––––––––+")
        return '\n'.join(lines) + '\n'

    def is_solved(self):
        # assure that every cell holds a single value between 1 and 9:
        if not all(k in "123456789" for k in self.solution.values()):
            return False

        # assure that every cell of every unit is unique in the proper unit:
        unitsolved = lambda u: set([self.solution[e] for e in u]) == set("123456789")
        return all(unitsolved(u) for u in self.unitlist)

def main(image=None):

    HARDEST = """
    +-------+-------+-------+
    | 8 0 0 | 0 0 0 | 0 0 0 |
    | 0 0 3 | 6 0 0 | 0 0 0 |
    | 0 7 0 | 0 9 0 | 2 0 0 |
    +-------+-------+-------+
    | 0 5 0 | 0 0 7 | 0 0 0 |
    | 0 0 0 | 0 4 5 | 7 0 0 |
    | 0 0 0 | 1 0 0 | 0 3 0 |
    +-------+-------+-------+
    | 0 0 1 | 0 0 0 | 0 6 8 |
    | 0 0 8 | 5 0 0 | 0 1 0 |
    | 0 9 0 | 0 0 0 | 4 0 0 |
    +-------+-------+-------+
    """

    PROBLEM_GRID = """
    +-------+-------+-------+
    | 0 0 0 | 0 0 0 | 0 0 1 |
    | 0 1 2 | 0 0 0 | 0 0 0 |
    | 0 0 0 | 0 0 0 | 2 0 0 |
    +-------+-------+-------+
    | 0 0 0 | 0 0 0 | 0 0 2 |
    | 0 2 0 | 0 0 0 | 0 0 0 |
    | 0 0 0 | 0 0 0 | 0 0 0 |
    +-------+-------+-------+
    | 0 0 0 | 0 0 0 | 1 2 0 |
    | 1 0 0 | 0 0 2 | 0 0 0 |
    | 0 0 0 | 1 0 0 | 0 0 0 |
    +-------+-------+-------+
    """

    CONST = """
    B9+B8+C1+H4+H4=23
    A5+D7+I5+G8+B3+A5=19
    I2+I3+F2+E9=15
    I7+H8+C2+D9=26
    I6+A5+I3+B8+C3=20
    I7+D9+B6+A8+A3+C4=27
    C7+H9+I7+B2+H8+G3=31
    D3+I8+A4+I6=27
    F5+B8+F8+I7+F1=33
    A2+A8+D7+E4=21
    C1+I4+C2+I1+A4=20
    F8+C1+F6+D3+B6=25
    """

    if image != None:
        try:
            print("\n[+] Extracting sudoku puzzle from: {}".format(image))
            img = load_image(image)
            predictions, sudoku_box_images, whole_sudoku_image = extract_sudoku(img)
            problem = predictions_to_suduko_string(predictions)
        except SudokuExtractError:
            print("[!] Could not extract Sudoku grid from the image: {}\n".format(image))
            exit(0)
    else:
        problem = HARDEST



    s = Sudoku(problem=problem)
    print("[+] Problem Puzzle:\n{}".format(s.get_grid(s.problem)))
    s.solve_z3()
    print("Solved: {}\n".format(s.is_solved()))
    print(s.get_side_by_side(s.problem,s.solution))

if __name__ == '__main__':

    parser = argparse.ArgumentParser()
    parser.add_argument("-img","--image", help="Image file containing the Sudoku puzzle")
    args = parser.parse_args()

    main(image=args.image)
from calculator.models import BeliefCalculator, BeliefType, Game, Player
import curses

# Constants for belief strengths
LOW_BELIEF = 0.3
HIGH_BELIEF = 0.6
KILLED_BELIEF = 0.9
KILLED_SHERIFF = 0.3
MAX_BELIEF = 1.0

# Define the belief strength mapping
belief_strength_mapping = {
    "+": LOW_BELIEF,
    "-": -LOW_BELIEF,
    "++": HIGH_BELIEF,
    "--": -HIGH_BELIEF,
    "+++": MAX_BELIEF,
    "---": -MAX_BELIEF,
    "k": KILLED_BELIEF,
    "ks": KILLED_SHERIFF
    }


def display_belief_matrix(stdscr, game, belief_calculator):
    # Calculate the belief matrix
    belief_matrix = belief_calculator.create_belief_matrix(game)

    # Display the header with player numbers
    header = "       "  # Start with some space for row labels
    for player_id in range(len(game.players)):
        header += f" P{player_id + 1}    "  # Assuming player_id starts at 0
    stdscr.addstr(0, 0, header)

    # Display the belief matrix with colors
    for i, row in enumerate(belief_matrix):
        # Add row label (player number)
        stdscr.addstr(i + 1, 0, f"P{i + 1} ", curses.color_pair(0))  # Row label for player i

        for j, belief in enumerate(row):
            color = curses.color_pair(1 if belief > 0.5 else 2 if belief < -0.5 else 0)
            # Calculate the horizontal position, accounting for the row label and spacing
            position_x = 5 + j * 7  # 5 spaces for row label, 7 for each belief value
            stdscr.addstr(i + 1, position_x, f"{belief:6.2f}", color)  # 6.2f for belief formatting

    # Calculate and display the sum of each column minus one
    column_sums = [sum(col) - 1 for col in zip(*belief_matrix)]
    sum_row_y = len(belief_matrix) + 2  # Position the sums one line below the matrix
    stdscr.addstr(sum_row_y, 0, "Sum-1")  # Label for the sum row
    for j, col_sum in enumerate(column_sums):
        position_x = 5 + j * 7  # Same horizontal position as the column values
        stdscr.addstr(sum_row_y, position_x, f"{col_sum:6.2f}")  # 6.2f for sum formatting

    # Refresh the screen to reflect the changes
    stdscr.refresh()


def display_input_lines(stdscr, app_state):
    # Calculate the vertical offset where the input lines start
    vertical_offset = (
            len(app_state.game.players) + 4
    )  # Adjust this if you have a header

    # Display the input lines for beliefs
    for player_id, player_lines in app_state.lines.items():
        for line_index, line in enumerate(player_lines):
            # Construct the line prefix and suffix
            prefix = f"{player_id + 1 if player_id < 9 else 0}:["
            suffix = "]"

            # Determine if the current line is selected
            is_selected = (
                    player_id == app_state.current_player
                    and line_index == app_state.current_line
            )

            # Choose the color based on whether the line is selected
            color = curses.color_pair(3 if is_selected else 0)

            # Calculate the vertical position for the current line
            vertical_position = (
                    vertical_offset
                    + sum(len(app_state.lines[i]) for i in range(player_id))
                    + line_index
            )

            # Display the line with the appropriate color
            stdscr.addstr(
                vertical_position,
                0,
                prefix + line.ljust(60) + suffix,
                color,
                )


class AppState:
    def __init__(self, num_players):
        self.num_players = num_players
        self.current_player = 0
        self.current_line = 0
        self.game = None
        self.lines = None
        self.selected_line_indices = None
        self.belief_calculator = None
        self.initialize_game(num_players)

    def initialize_game(self, num_players):
        # Initialize the game with players
        players = [Player(player_id=i) for i in range(num_players)]
        self.game = Game(players)
        self.belief_calculator = BeliefCalculator(self.game)

        # Set up curses environment
        curses.curs_set(1)  # Make the cursor visible
        curses.noecho()  # Do not echo keystrokes
        curses.start_color()  # Initialize colors

        # Initialize the position of the cursor and the lines for each player
        self.lines = {player.player_id: [""] for player in players}
        self.selected_line_indices = {player.player_id: 0 for player in players}

        # Initialize color pairs
        curses.init_pair(1, curses.COLOR_GREEN, curses.COLOR_BLACK)
        curses.init_pair(2, curses.COLOR_RED, curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_CYAN, curses.COLOR_BLACK)


def position_cursor(stdscr, app_state):
    # Calculate the vertical position by summing the number of lines for each player
    # up to the current player, then add the current line within that player's workspace
    vertical_position = (
            sum(len(app_state.lines[i]) for i in
                range(app_state.current_player)) + app_state.num_players + 2
    )
    vertical_position += app_state.current_line + 2  # +2 for the header offset

    # Calculate the horizontal position based on the length of the current line
    # +3 accounts for the prefix "1:[" which is 3 characters long
    horizontal_position = (
            len(app_state.lines[app_state.current_player][app_state.current_line]) + 3
    )

    # Move the cursor to the calculated position
    stdscr.move(vertical_position, horizontal_position)


def add_player_line(app_state):
    # Add a new empty line to the current player's list of lines
    app_state.lines[app_state.current_player].append("")

    # Update the current_line index to point to the new line
    app_state.current_line = len(app_state.lines[app_state.current_player]) - 1


def kill_player(stdscr, app_state, sheriff=False):
    if app_state.game.players[app_state.current_player].alive:
        current_player_backup = app_state.current_player
        for player_id, value_block in app_state.lines.items():
            if sheriff:
                value_block[-1] += f" {current_player_backup + 1}ks "
            else:
                value_block[-1] += f" {current_player_backup + 1}k "
            app_state.current_player = player_id
            process_input_lines(stdscr, app_state)
        app_state.game.players[current_player_backup].alive = False
        app_state.current_player = current_player_backup



def handle_user_input(stdscr, key, app_state):
    if key == curses.KEY_UP:
        if app_state.current_line > 0:
            app_state.current_line -= 1
        elif app_state.current_player > 0:
            app_state.current_player -= 1
            app_state.current_line = len(app_state.lines[app_state.current_player]) - 1

    elif key == curses.KEY_DOWN:
        if app_state.current_line < len(app_state.lines[app_state.current_player]) - 1:
            app_state.current_line += 1
        elif app_state.current_player < len(app_state.game.players) - 1:
            app_state.current_player += 1
            app_state.current_line = 0
    elif key == ord("k"):
        # Killed player
        kill_player(stdscr, app_state)
    elif key == ord("s"):
        # Killed player
        kill_player(stdscr, app_state, sheriff=True)
    elif key == ord("a"):  # Add a new belief row for the current player
        add_player_line(app_state)
    elif key == ord("d"):  # Delete the selected belief row for the current player
        delete_selected_line(stdscr, app_state)
    elif key == curses.KEY_ENTER or key == 10 or key == 13:  # Enter key
        process_input_lines(stdscr, app_state)
    elif key == curses.KEY_BACKSPACE:
        modify_characters_in_line(
            stdscr,
            app_state,
            chr(key),
            backspace=True
            )
    elif 32 <= key <= 126:  # Printable characters
        modify_characters_in_line(
            stdscr,
            app_state,
            chr(key),
            )


def delete_selected_line(stdscr, app_state):
    current_player = app_state.current_player
    player_lines = app_state.lines[current_player]

    if player_lines and app_state.current_line > 0:
        # Delete the selected line from the player's list of lines
        player_lines.pop(app_state.current_line)

        # Update the current_line index to the previous line or to the last line if it was the
        # first line
        app_state.current_line = max(app_state.current_line - 1, 0)

        # Calculate the position of the last line on the screen
        last_line_y = (
                sum(len(lines) for lines in app_state.lines.values()) + 1
        )  # +1 for the header offset
        # Move to the last line and clear it
        old_y, old_x = stdscr.getyx()
        stdscr.move(last_line_y, 0)
        stdscr.clrtoeol()
        stdscr.move(old_y, old_x)
        # Refresh the screen to reflect the changes
        stdscr.clear()
        stdscr.refresh()


def modify_characters_in_line(stdscr, app_state, char, backspace=False):
    current_player = app_state.current_player
    current_line = app_state.current_line
    player_lines = app_state.lines[current_player]
    selected_line = player_lines[current_line]

    extra_sum_offset = 2
    # If the line was processed (cyan), change it back to white
    line_y_position = len(app_state.game.players) + current_player + current_line + 2 +extra_sum_offset
    if stdscr.inch(line_y_position, 0) & curses.A_COLOR == curses.color_pair(4):
        stdscr.chgat(line_y_position, 0, curses.color_pair(3))

    if backspace:
        player_lines[current_line] = player_lines[current_line][:-1]
    else:
        # Add the character to the selected line
        player_lines[current_line] += char

    # Update the display of the line
    prefix = f"{current_player + 1 if current_player < 9 else 0}:["
    suffix = "]"
    stdscr.addstr(
        line_y_position,
        0,
        prefix + selected_line.ljust(60) + suffix,
        curses.color_pair(3),
        )


def main(stdscr):
    app_state = AppState(10)  # Example with 5 players

    # Main loop
    while True:
        # Display the belief matrix and the input lines
        display_belief_matrix(stdscr, app_state.game, app_state.belief_calculator)
        display_input_lines(stdscr, app_state)

        # Position the cursor at the end of the current line
        position_cursor(stdscr, app_state)

        # Get user input
        key = stdscr.getch()

        # Handle user input
        handle_user_input(stdscr, key, app_state)

        # Refresh the screen
        stdscr.refresh()


def process_input_lines(stdscr, app_state):
    player_id = app_state.current_player
    player_lines = app_state.lines[player_id]
    # Clear existing beliefs for the player
    app_state.game.players[player_id].beliefs.clear()

    # Process all input lines for the player and update beliefs
    for line in player_lines:
        parts = line.split()
        for part in parts:
            # Find the index where the digits end and the belief code starts
            index = next(
                (i for i, char in enumerate(part) if not char.isdigit()), len(part)
                )
            try:
                target_player_id = int(part[:index]) - 1  # Convert to zero-based index
                if target_player_id >= app_state.num_players or target_player_id < 0:
                    raise ValueError
                belief_code = part[index:]
                if belief_code in belief_strength_mapping:
                    belief_strength = belief_strength_mapping[belief_code]
                    belief_type = (
                        BeliefType.RED if belief_strength > 0 else BeliefType.BLACK
                    )
                    app_state.game.players[player_id].record_belief(
                        target_player_id, belief_type, abs(belief_strength)
                        )
            except (ValueError, IndexError):
                pass  # Ignore invalid input
    vertical_offset = len(app_state.game.players) + 2  # Adjust if you have a header
    line_y_position = (
            vertical_offset
            + sum(len(app_state.lines[i]) for i in range(player_id))
            + app_state.current_line
    )
    # Change the color of the current processed line
    stdscr.chgat(
        line_y_position,  # Correct y position for the current line
        0,  # x position (start of the line)
        -1,  # -1 means apply the attribute change across the entire line
        curses.color_pair(4),  # Color pair for processed lines
        )

    # Refresh the screen to reflect the changes
    stdscr.refresh()


if __name__ == "__main__":
    # Run the curses application
    curses.wrapper(main)

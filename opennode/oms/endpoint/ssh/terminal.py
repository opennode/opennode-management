import os
import string

from twisted.conch import recvline
from twisted.conch.insults.insults import modes
from twisted.python import log


CTRL_A = '\x01'
CTRL_C = '\x03'
CTRL_E = '\x05'
CTRL_D = '\x04'
CTRL_K = '\x0b'
CTRL_Y = '\x19'
CTRL_BACKSLASH = '\x1c'
CTRL_L = '\x0c'
CTRL_T = '\x14'
CTRL_R = '\x12'
CTRL_G = '\x07'

BLUE = '\x1b[1;34m'
CYAN = '\x1b[1;36m'
GREEN = '\x1b[1;32m'

RESET_COLOR = '\x1b[0m'


class InteractiveTerminal(recvline.HistoricRecvLine):
    """Advanced interactive terminal. Handles history, line editing, killing/yanking, line movement.

    Prompt handling is delegated to subclasses.

    """

    def connectionMade(self):
        super(InteractiveTerminal, self).connectionMade()

        self.enable_colors = True
        self.history_save_enabled = True
        self.restore_history()

        self.kill_ring = None
        self.keyHandlers[CTRL_A] = self.handle_HOME
        self.keyHandlers[CTRL_E] = self.handle_END
        self.keyHandlers[CTRL_D] = self.handle_EOF
        self.keyHandlers[CTRL_L] = self.handle_FF
        self.keyHandlers[CTRL_K] = self.handle_KILL_LINE
        self.keyHandlers[CTRL_Y] = self.handle_YANK
        self.keyHandlers[CTRL_T] = self.handle_TRANSPOSE
        self.keyHandlers[CTRL_R] = self.handle_SEARCH
        self.keyHandlers[CTRL_G] = self.handle_ABORT
        self.keyHandlers[CTRL_BACKSLASH] = self.handle_QUIT

        self.altKeyHandlers = {self.terminal.BACKSPACE: self.handle_BACKWARD_KILL_WORD}

        self.search_mode = False
        self.found_index = -1
        self.search_skip = 0

        self.terminal.reset()
        self.terminal.setModes((modes.IRM, ))

    def set_terminal(self, terminal):
        self.terminal = terminal
        terminal.terminalProtocol = self

    def keystrokeReceived(self, keyID, modifier):
        if self.search_mode:
            if keyID == '\n' or keyID == '\r':
                return self.handle_SEARCH_RETURN()

            if keyID == CTRL_R:
                return self.handle_SEARCH_NEXT()
            self.search_skip = 0

            if not (keyID == CTRL_G or keyID == self.terminal.BACKSPACE or (isinstance(keyID, str) and keyID in string.printable)):
                self.handle_EXIT_SEARCH()
                # Fall through, continue processing

        if modifier == self.terminal.ALT:
            m = self.altKeyHandlers.get(keyID)
            if m is not None:
                m()
            return

        super(InteractiveTerminal, self).keystrokeReceived(keyID, modifier)

        if self.search_mode:
            self.handle_UPDATE_SEARCH()

    def restore_history(self):
        try:
            if os.path.exists(self.hist_file_name):
                self.historyLines = [line.strip() for line in open(self.hist_file_name, 'r').readlines()]
                self.historyPosition = len(self.historyLines)
        except Exception as e:
            log.msg("cannot restore history: %s" % e)

    def save_history(self):
        if not self.history_save_enabled:
            return

        try:
            concat = [line + '\n' for line in self.historyLines]
            with open(self.hist_file_name, 'w') as f:
                f.writelines(concat)
        except Exception as e:
            log.msg("cannot save history: %s" % e)

    @property
    def hist_file_name(self):
        raise NotImplementedError

    def print_prompt(self):
        self.terminal.write(self.ps[self.pn])

    def insert_buffer(self, buf):
        """Inserts some chars in the buffer at the current cursor position."""
        lead, rest = self.lineBuffer[0:self.lineBufferIndex], self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = lead + buf + rest
        self.lineBufferIndex += len(buf)

    def insert_text(self, text):
        """Inserts some text at the current cursor position and renders it."""
        if isinstance(text, unicode):
            text = text.encode('utf-8')
        self.terminal.write(text)
        self.insert_buffer(list(text))

    def handle_EOF(self):
        """Exits the shell on CTRL-D"""
        if self.lineBuffer:
            self.terminal.write('\a')
        else:
            self.handle_QUIT()

    def handle_FF(self):
        """Handles a 'form feed' byte - generally used to request a screen refresh/redraw."""
        self.terminal.eraseDisplay()
        self.terminal.cursorHome()
        self.drawInputLine()

    def handle_KILL_LINE(self):
        """Deletes the rest of the line (from the cursor right), and
        keeps the content in the kill ring for future pastes.

        """
        self.terminal.eraseToLineEnd()
        self.kill_ring = self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = self.lineBuffer[0:self.lineBufferIndex]

    def handle_YANK(self):
        """Pastes the content of the kill ring."""
        if self.kill_ring:
            self.terminal.write("".join(self.kill_ring))
            self.insert_buffer(self.kill_ring)

    def handle_BACKWARD_KILL_WORD(self):
        """Provides the ALT-BACKSPACE behaviour like in emacs/bash."""

        line = ''.join(self.lineBuffer[:self.lineBufferIndex])

        # remove trailing spaces
        back_positions = len(line) - len(line.rstrip())
        line = line.rstrip()

        # remove everthing until the previous space (not included)
        back_positions += len(line) - (' ' + line).rfind(' ')

        self.terminal.cursorBackward(back_positions)
        self.terminal.deleteCharacter(back_positions)

        # XXX: The index value should be extracted to a local variable for readability and DRY
        self.kill_ring = self.lineBuffer[self.lineBufferIndex - back_positions : self.lineBufferIndex]
        del self.lineBuffer[self.lineBufferIndex - back_positions : self.lineBufferIndex]
        self.lineBufferIndex -= back_positions

    def handle_TRANSPOSE(self):
        """Provides the CTRL-T behaviour like on emacs/bash."""

        if self.lineBufferIndex == 0:
            self.terminal.cursorForward()
            self.lineBufferIndex += 1

        if self.lineBufferIndex == len(self.lineBuffer):
            self.terminal.cursorBackward()
            self.lineBufferIndex -= 1

        if self.lineBufferIndex > 0 and self.lineBufferIndex < len(self.lineBuffer) and len(self.lineBuffer) > 1:
            l, r = self.lineBuffer[self.lineBufferIndex - 1], self.lineBuffer[self.lineBufferIndex]

            self.lineBuffer[self.lineBufferIndex - 1] = r
            self.lineBuffer[self.lineBufferIndex] = l
            self.terminal.cursorBackward()
            self.terminal.deleteCharacter(2)
            self.terminal.write(r + l)

            self.lineBufferIndex += 1

    @property
    def search_ps(self):
        return "bck-i-search: "

    def handle_SEARCH(self):
        self.search_mode = True
        self.found_index = -1
        self.terminal.write('\n' + self.search_ps)
        self.lineBuffer = []
        self.lineBufferIndex = 0
        self.search_skip = 0

    def handle_UPDATE_SEARCH(self, skip=0):
        needle = ''.join(self.lineBuffer)
        self.found_index = -1
        found_hist = ''

        for hist, pos in reversed(zip(self.historyLines, xrange(0, len(self.historyLines)))):
            if needle in hist:
                self.found_index = pos
                if skip > 0:
                    skip -= 1
                    continue

                found_hist = hist
                break

        if self.found_index < 0:
            return

        # Go up the previous line after prompt
        self.terminal.cursorBackward(self.lineBufferIndex + len(self.search_ps))
        self.terminal.cursorUp()
        self.terminal.cursorForward(len(self.ps[self.pn]))
        self.terminal.eraseToLineEnd()

        self.terminal.write(found_hist)

        # Go back to where we left editing the search expression.

        self.terminal.cursorBackward(len(self.ps[self.pn]) + len(found_hist))
        self.terminal.cursorDown()
        self.terminal.cursorForward(self.lineBufferIndex + len(self.search_ps))

    def handle_SEARCH_NEXT(self):
        self.search_skip += 1
        self.handle_UPDATE_SEARCH(self.search_skip)

    def handle_EXIT_SEARCH(self):
        """Exits search mode and edit the found history line."""
        self.search_mode = False

        needle = ''.join(self.lineBuffer)
        hist = self.historyLines[self.found_index]

        self.terminal.cursorBackward(self.lineBufferIndex + len(self.search_ps))
        self.terminal.eraseToLineEnd()
        self.terminal.cursorUp()
        self.terminal.cursorForward(len(self.ps[self.pn]) + hist.find(needle))

        self.lineBuffer = list(hist)
        self.lineBufferIndex = hist.find(needle)
        self.historyPosition = self.found_index

    def handle_SEARCH_RETURN(self):
        self.search_mode = False
        self.terminal.write('\n')

        if self.found_index < 0:
            self.print_prompt()
            return

        self.lineBuffer = []
        self.lineBufferIndex = 0

        # record it in the history
        self.historyLines.append(self.historyLines[self.found_index])
        self.historyPosition = len(self.historyLines)

        self.lineReceived(self.historyLines[self.found_index])

    def handle_ABORT(self):
        """Abort a search."""
        if self.search_mode:
            self.search_mode = False

            self.terminal.cursorBackward(self.lineBufferIndex + len(self.search_ps))
            self.terminal.eraseToLineEnd()
            self.terminal.cursorUp(1)
            self.terminal.eraseToLineEnd()
            self.lineBuffer = []
            self.lineBufferIndex = 0
            self.drawInputLine()

    def handle_QUIT(self):
        """Just copied from conch Manhole, no idea why it would be useful to differentiate it from CTRL-D,
        but I guess it's here for a reason.

        """
        self.close_connection()

    def colorize(self, color, text):
        return (color + text + RESET_COLOR
                if color and self.enable_colors
                else text)

    def close_connection(self):
        """Closes the connection and saves history."""

        self.save_history()
        self.terminal.loseConnection()

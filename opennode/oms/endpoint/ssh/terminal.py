import os

from twisted.conch import recvline
from twisted.python import log


CTRL_A = '\x01'
CTRL_E = '\x05'
CTRL_D = '\x04'
CTRL_K = '\x0b'
CTRL_Y = '\x19'
CTRL_BACKSLASH = '\x1c'
CTRL_L = '\x0c'
CTRL_T = '\x14'

BLUE = '\x1b[1;34m'
RESET_COLOR = '\x1b[0m'

class InteractiveTerminal(recvline.HistoricRecvLine):
    """Advanced interactive terminal. Handles history, line editing,
    killing/yanking, line movement.

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
        self.keyHandlers[CTRL_BACKSLASH] = self.handle_QUIT

        self.altKeyHandlers = {self.terminal.BACKSPACE: self.handle_BACKWARD_KILL_WORD}

    def keystrokeReceived(self, keyID, modifier):
        if modifier == self.terminal.ALT:
            m = self.altKeyHandlers.get(keyID)
            if m is not None:
                m()
            return

        return super(InteractiveTerminal, self).keystrokeReceived(keyID, modifier)

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
            open(self.hist_file_name, 'w').writelines([line + '\n' for line in self.historyLines])
        except Exception as e:
            log.msg("cannot save history: %s" % e)

    @property
    def hist_file_name(self):
        raise Exception("subclass must override")

    def print_prompt(self):
        self.terminal.write(self.ps[self.pn])

    def insert_buffer(self, buf):
        """Inserts some chars in the buffer at the current cursor position."""
        lead, rest = self.lineBuffer[0:self.lineBufferIndex], self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = lead + buf + rest
        self.lineBufferIndex += len(buf)

    def insert_text(self, text):
        """Inserts some text at the current cursor position and renders it."""
        self.terminal.write(text)
        self.insert_buffer(list(text))

    def handle_EOF(self):
        """Exit the shell on CTRL-D"""
        if self.lineBuffer:
            self.terminal.write('\a')
        else:
            self.handle_QUIT()

    def handle_FF(self):
        """Handle a 'form feed' byte - generally used to request a screen
        refresh/redraw.
        """
        self.terminal.eraseDisplay()
        self.terminal.cursorHome()
        self.drawInputLine()

    def handle_KILL_LINE(self):
        """Deletes the rest of the line (from the cursor right), and keeps the content
        in the kill ring for future pastes
        """
        self.terminal.eraseToLineEnd()
        self.kill_ring = self.lineBuffer[self.lineBufferIndex:]
        self.lineBuffer = self.lineBuffer[0:self.lineBufferIndex]

    def handle_YANK(self):
        """Paste the content of the kill ring"""
        if self.kill_ring:
            self.terminal.write("".join(self.kill_ring))
            self.insert_buffer(self.kill_ring)

    def handle_BACKWARD_KILL_WORD(self):
        """ALT-BACKSPACE like on emacs/bash."""

        line = "".join(self.lineBuffer[:self.lineBufferIndex])

        # remove trailing spaces
        back_positions = len(line) - len(line.rstrip())
        line = line.rstrip()

        # remove everthing until the previous space (not included)
        back_positions += len(line) - (' ' + line).rfind(' ')

        self.terminal.cursorBackward(back_positions)
        self.terminal.deleteCharacter(back_positions)

        self.kill_ring = self.lineBuffer[self.lineBufferIndex - back_positions : self.lineBufferIndex]
        del self.lineBuffer[self.lineBufferIndex - back_positions : self.lineBufferIndex]
        self.lineBufferIndex -= back_positions

    def handle_TRANSPOSE(self):
        """CTRL-T like on emacs/bash."""

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

    def handle_QUIT(self):
        """Just copied from conch Manhole, no idea why it would be useful to differentiate it from CTRL-D,
        but I guess it's here for a reason"""
        self.close_connection()

    def colorize(self, color, text):
        return color + text + RESET_COLOR if self.enable_colors else text

    def close_connection(self):
        """Closes the connection and saves history."""

        self.save_history()
        self.terminal.loseConnection()

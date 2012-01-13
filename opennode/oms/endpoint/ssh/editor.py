from twisted.internet import defer
from twisted.conch.insults import insults
from twisted.python import log

from opennode.oms.util import exception_logger
from opennode.oms.endpoint.ssh.terminal import CTRL_C, CTRL_D, CTRL_X, CTRL_S, CTRL_G, CTRL_L


class Editor(object):
    def __init__(self, parent):
        self.parent = parent
        self.terminal = parent.terminal
        self.buffer = ""
        self.status_line = ""

        self.prefix = None
        self.prefixes = [CTRL_X]
        self.key_handlers = {(CTRL_X, CTRL_S): self.handle_SAVE,
                             (CTRL_X, CTRL_C): self.handle_EXIT,
                             (CTRL_X, '='): self.handle_WHAT_CURSOR_POSITION,
                             CTRL_D: self.terminal.deleteCharacter,
                             CTRL_L: self.handle_REDRAW,
                             self.terminal.LEFT_ARROW: self.handle_LEFT,
                             self.terminal.RIGHT_ARROW: self.handle_RIGHT,
                             self.terminal.UP_ARROW: self.handle_UP,
                             self.terminal.DOWN_ARROW: self.handle_DOWN,
                             self.terminal.BACKSPACE: self.handle_BACKSPACE}

    @defer.inlineCallbacks
    def start(self, file):
        self.buffer = file

        # position in buffer
        self.pos = 0
        # current line in buffer
        self.current_line = 0
        self.lines = self.buffer.count('\n') + 1

        self.parent.sub_protocol = self

        self.parent.enter_full_screen()
        self.terminal.write('\x1b[?7l')  # disable auto wrap
        self.terminal.write('\x1b[0;%sr' % (self.parent.height - 2,))  # setup scrolling region
        self.terminal.termSize.y -= 2

        try:
            self.redraw_buffer()
            self.terminal.cursorHome()

            yield self.wait_for_exit()
        finally:
            self.terminal.termSize.y += 2
            self.terminal.write('\x1b[?7h') # re-enable auto wrap
            self.parent.exit_full_screen()

        defer.returnValue(self.buffer)

    def wait_for_exit(self):
        self.exit = defer.Deferred()
        return self.exit

    def redraw_buffer(self):
        self.terminal.saveCursor()

        self.terminal.eraseDisplay()
        self.draw_modeline('--:-- test     0 % (0,0) (Fundamental)')
        self.terminal.cursorHome()

        self.terminal.write('\n'.join(self.buffer.split('\n')[0:self.parent.height-2]))

        self.terminal.restoreCursor()

    def draw_modeline(self, text):
        self.terminal.cursorPosition(0, self.parent.height - 2)
        self.terminal.selectGraphicRendition(str(insults.REVERSE_VIDEO))
        self.terminal.write(text.ljust(self.parent.width))
        self.terminal.selectGraphicRendition()

    def draw_status(self, text):
        if text == self.status_line:
            return
        self.status_line = text

        self.terminal.saveCursor()
        self.terminal.cursorPosition(0, self.parent.height - 1)
        self.terminal.eraseLine()
        self.terminal.write(text)
        self.terminal.restoreCursor()

    def abort(self):
        self.prefix = ""
        self.draw_status("Quit")

    def char_at(self, pos):
        return self.buffer[pos] if pos < len(self.buffer) else '\x00'

    def handle_EOF(self):
        pass

    def handle_EXIT(self):
        self.exit.callback(None)

    def handle_SAVE(self):
        self.draw_status("Object saved")

    def handle_WHAT_CURSOR_POSITION(self):
        ch = self.char_at(self.pos)
        pch = self.char_at(self.pos - 1) if self.pos else '\x00'
        nch = self.char_at(self.pos + 1) if self.pos + 1 < len(self.buffer) else '\x00'

        bol_pos = self.bol_pos()
        eol_pos = self.eol_pos()

        if self.pos:
            if self.char_at(self.pos - 1) == '\n':
                prev_line = self.bol_pos(self.pos - 1)
            else:
                prev_line = self.bol_pos(self.bol_pos() - 2)
        else:
            prev_line = 0

        next_line = self.eol_pos() + 1

        self.draw_status('Char: %s (%s %s) point=%s of %s line=%s; Prev: %s (%s %s), Next: %s (%s %s) bol=%s eol=%s prev_line=%s next_line=%s' %
                         (self.show_keys((ch,)), ord(ch), hex(ord(ch)),
                          self.pos, len(self.buffer), self.current_line,
                          self.show_keys(pch,), ord(pch), hex(ord(pch)),
                          self.show_keys(nch,), ord(nch), hex(ord(nch)),
                          bol_pos, eol_pos, prev_line, next_line
                         ))

    def handle_BACKSPACE(self):
        self.terminal.cursorBackward()
        self.terminal.deleteCharacter()

    def _rfind(self, string, sub, start=None, end=None):
        """Behaves like str.find, but returns 0 instead of -1"""
        res = string.rfind(sub, start, end)
        return res if res != -1 else 0

    def _find(self, string, sub, start=None, end=None):
        """Behaves like str.find, but returns last_pos instead of -1"""
        res = string.find(sub, start, end)
        return res if res != -1 else len(self.buffer) - 1

    def bol_pos(self, from_pos=None):
        if from_pos == None:
            from_pos = self.pos
        return self.buffer.rfind('\n', 0, from_pos) + 1

    def eol_pos(self):
        return self._find(self.buffer, '\n', self.pos)

    def handle_LEFT(self):
        if not self.pos:
            return

        if self.char_at(self.pos - 1) == '\n':
            self.goto_prev_line()
            go_forward = self.eol_pos() - self.pos

            # twisted insults cannot move by 0 amount
            if go_forward:
                self.terminal.cursorForward(go_forward)
                self.pos += go_forward
        else:
            self.terminal.cursorBackward()
            self.pos -= 1

    def handle_RIGHT(self):
        if self.pos >= len(self.buffer):
            return

        if self.char_at(self.pos) == '\n':
            go_back = self.pos - self.bol_pos()
            self.goto_next_line()

            # twisted insults cannot move by 0 amount
            if go_back:
                self.terminal.cursorBackward(go_back)
        else:
            self.pos += 1
            self.terminal.cursorForward()

    def handle_UP(self):
        go_forward = self.pos - self.bol_pos()
        self.goto_prev_line()

        self.fixup_for_shorter_line(go_forward)

    def goto_prev_line(self):
        # reached the top of the file
        if self.current_line == 0:
            return
        self.current_line = self.current_line - 1

        if self.char_at(self.pos - 1) == '\n':
            self.pos = self.bol_pos(self.pos - 1)
        else:
            self.pos = self.bol_pos(self.bol_pos() - 2)


        should_fill = self.terminal.cursorPos.y == 0

        # move and possibly scroll
        self.terminal.reverseIndex()

        if should_fill:
            self.terminal.saveCursor()
            self.terminal.write(self.buffer[self.pos:self.eol_pos()])
            self.terminal.restoreCursor()

    def handle_DOWN(self):
        go_forward = self.pos - self.bol_pos()
        self.goto_next_line()

        self.fixup_for_shorter_line(go_forward)

    def fixup_for_shorter_line(self, go_forward):
        line_length = max(0, self.eol_pos() - self.bol_pos())
        self.pos += min(go_forward, line_length)

        # fixup screen cursor position in case of out of range
        move_backward = go_forward - min(go_forward, line_length)
        if move_backward:
            self.terminal.cursorBackward(move_backward)

    def goto_next_line(self):
        # reached the end of the file
        if self.current_line >= self.lines - 1:
            return
        self.current_line = self.current_line + 1
        self.pos = self.eol_pos() + 1

        should_fill = self.terminal.cursorPos.y == self.terminal.termSize.y - 1

        # move and possibly scroll
        self.terminal.index()

        if should_fill:
            self.terminal.saveCursor()
            self.terminal.write(self.buffer[self.pos:self.eol_pos()])
            self.terminal.restoreCursor()

    def handle_REDRAW(self):
        self.redraw_buffer()

    def show_keys(self, keys, prefix='C-'):
        def show_key(key):
            if ord(key) == 127:
                return '^H'
            if ord(key) < 32 and key != '\r':
                return prefix + chr(ord('A') + ord(key) - 1)
            return key
        return "-".join(show_key(key) for key in keys)

    def _echo(self, keyID, mod):
        """Echoes characters on terminal like on unix (special chars etc)"""
        if isinstance(keyID, str):
            self.terminal.write(self.show_keys((keyID, ), prefix='^'))

            if keyID in ('\r'):
                self.terminal.write('\n')
                self.lines = self.lines + 1
                self.current_line = self.current_line + 1
        else:
            log.msg("GOT Special char '%s' (%s)" % (keyID, type(keyID)))

    @exception_logger
    def keystrokeReceived(self, keyID, mod):
        if keyID == CTRL_G:
            self.abort()
        elif self.prefix:
            handler = self.key_handlers.get((self.prefix, keyID), None)
            try:
                if handler:
                    self.draw_status("")
                    handler()
                else:
                    self.draw_status("%s is undefined" % self.show_keys((self.prefix, keyID)))
            finally:
                self.prefix = None
        elif keyID in self.prefixes:
            self.prefix = keyID
            self.draw_status(self.show_keys(keyID))
        elif self.key_handlers.get(keyID, None):
            self.key_handlers.get(keyID, None)()
        else:
            self.draw_status("")
            self._echo(keyID, mod)

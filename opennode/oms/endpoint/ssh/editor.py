import os

from contextlib import closing
from copy import copy
from twisted.internet import defer
from twisted.conch.insults import insults
from twisted.python import log

from opennode.oms.util import exception_logger, find_nth
from opennode.oms.endpoint.ssh.terminal import CTRL_A, CTRL_C, CTRL_E, CTRL_K, CTRL_X, CTRL_S, CTRL_G, CTRL_L, CTRL_W


class Editor(object):

    MODELINE_HEIGHT = 2

    def __init__(self, parent):
        self.parent = parent
        self.terminal = parent.terminal
        self.buffer = ""
        self.old_dirty = False
        self.dirty = False
        self.status_line = ""
        self.has_quit = False

        self.prefix = None
        self.prefixes = [CTRL_X]
        self.key_handlers = {(CTRL_X, CTRL_S): self.handle_SAVE,
                             (CTRL_X, CTRL_W): self.handle_DUMP_BUFFER,
                             (CTRL_X, CTRL_C): self.handle_EXIT,
                             (CTRL_X, '='): self.handle_WHAT_CURSOR_POSITION,
                             CTRL_A: self.handle_BEGIN_LINE,
                             CTRL_E: self.handle_END_LINE,
                             CTRL_K: self.handle_KILL_LINE,
                             CTRL_L: self.handle_REDRAW,
                             self.terminal.LEFT_ARROW: self.handle_LEFT,
                             self.terminal.RIGHT_ARROW: self.handle_RIGHT,
                             self.terminal.UP_ARROW: self.handle_UP,
                             self.terminal.DOWN_ARROW: self.handle_DOWN,
                             self.terminal.BACKSPACE: self.handle_BACKSPACE}

    def reset_scrolling_region(self):
        self.terminal.setScrollRegion(last=self.parent.height - self.MODELINE_HEIGHT)

    @defer.inlineCallbacks
    def start(self, file):
        self.tracing = False

        self.buffer = file
        self.saved = copy(self.buffer)

        # position in buffer
        self.pos = 0
        # current line in buffer
        self.current_line = 0
        self.current_column = 0
        self.lines = self.buffer.count('\n') + 1

        self.parent.sub_protocol = self

        self.parent.enter_full_screen()
        self.terminal.write('\x1b[?7l')  # disable auto wrap
        self.reset_scrolling_region()
        self.parent.setInsertMode()
        self.terminal.termSize.y -= 2

        if self.tracing:
            self.enable_tracing()

        try:
            self.redraw_buffer()
            self.terminal.cursorHome()

            if self.tracing:
                self.replay_recorded()

            yield self.wait_for_exit()
        finally:
            self.terminal.termSize.y += 2
            self.terminal.write('\x1b[?7h') # re-enable auto wrap
            self.parent.exit_full_screen()

            if self.tracing:
                self.finalize_tracing()

        defer.returnValue(self.saved)

    def replay_recorded(self):
        """Debug utility useful for repeating difficult to reproduce sessions that show some bug"""
        replay_file = '/tmp/key.sim'
        if os.path.exists(replay_file):
            arrows = {'[UP_ARROW]': self.terminal.UP_ARROW,
                      '[DOWN_ARROW]': self.terminal.DOWN_ARROW,
                      '[LEFT_ARROW]': self.terminal.LEFT_ARROW,
                      '[RIGHT_ARROW]': self.terminal.RIGHT_ARROW,
                      }
            for i in open(replay_file):
                if '#' not in i:
                    self.keystrokeReceived(arrows[i.strip()], None)

    def enable_tracing(self):
        self.tracing = True
        self.key_log = open('/tmp/key.log', 'w')

    def finalize_tracing(self):
        self.key_log.close()

    def trace_keystroke(self, keyID, mod):
        if self.tracing:
            print >>self.key_log, keyID
            self.key_log.flush()

    def wait_for_exit(self):
        self.exit = defer.Deferred()
        return self.exit

    def redraw_buffer(self):
        self.terminal.saveCursor()

        self.terminal.eraseDisplay()
        self.draw_modeline('--:-- test     0 %  (0,0)      (Fundamental)')
        self.terminal.cursorHome()

        self.terminal.write('\n'.join(self.buffer.split('\n')[0:self.parent.height-2]))

        self.terminal.restoreCursor()

    def draw_modeline(self, text):
        self.terminal.cursorPosition(0, self.parent.height - 2)
        self.terminal.selectGraphicRendition(str(insults.REVERSE_VIDEO))
        self.terminal.write(text.ljust(self.parent.width))
        self.terminal.selectGraphicRendition()

    def refresh_modline(self):
        if self.has_quit:
            return

        self.terminal.saveCursor()
        self.terminal.selectGraphicRendition(str(insults.REVERSE_VIDEO))
        self.parent.setTypeoverMode()

        if self.dirty != self.old_dirty:
            self.old_dirty = self.dirty
            self.terminal.cursorPosition(3, self.parent.height - 2)
            if self.dirty:
                self.terminal.write('**')
            else:
                self.terminal.write('--')

        self.terminal.cursorPosition(20, self.parent.height - 2)
        self.terminal.write('(%s,%s)   ' % (self.current_line, self.current_column))

        self.parent.setInsertMode()
        self.terminal.selectGraphicRendition()
        self.terminal.restoreCursor()

    def draw_status(self, text):
        text = text.replace('\n', '^J')

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
        self.has_quit = True
        self.exit.callback(None)

    def handle_SAVE(self):
        self.draw_status("Object saved")
        self.saved = copy(self.buffer)
        self.dirty = False

    def handle_DUMP_BUFFER(self):
        self.draw_status("Buffer dumped to /tmp/dump.txt")
        with closing(open('/tmp/dump.txt', 'w')) as f:
            print >>f, self.buffer,

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

        self.draw_status('Char: %s (%s %s) point=%s of %s line=%s; Prev: %s (%s %s), Next: %s (%s %s) bol=%s eol=%s prev_line=%s next_line=%s cursor=(%s, %s)' %
                         (self.show_keys((ch,)), ord(ch), hex(ord(ch)),
                          self.pos, len(self.buffer), self.current_line,
                          self.show_keys(pch,), ord(pch), hex(ord(pch)),
                          self.show_keys(nch,), ord(nch), hex(ord(nch)),
                          bol_pos, eol_pos, prev_line, next_line,
                          self.terminal.cursorPos.y, self.terminal.cursorPos.x
                         ))

    def handle_BACKSPACE(self):
        if not self.pos:
            return
        # currently we have to have a trailing newline
        if self.pos == len(self.buffer):
            return

        self.dirty = True

        # currently hitting backspace at the beginning of a line is not implemented
        if self.pos == self.bol_pos():
            self.terminal.eraseToLineEnd()
            self.terminal.saveCursor()

            # scroll up part below deleted line
            # XXX: consider using termSize.y instead of computing view size using MODELINE_HEIGHT
            current_screen_line = self.terminal.cursorPos.y
            self.terminal.setScrollRegion(current_screen_line + 1, self.parent.height - self.MODELINE_HEIGHT)
            self.terminal.cursorPosition(0, self.parent.height - self.MODELINE_HEIGHT - 1)
            self.terminal.index()

            # redraw revealed line
            self.terminal.cursorPosition(0, self.parent.height - self.MODELINE_HEIGHT - 1)

            last_line_delta = self.terminal.termSize.y - self.terminal.cursorPos.y +  1
            last_line_pos = find_nth(self.buffer, '\n', last_line_delta, self.pos)

            if last_line_pos > 0:
                last_line_end = self.buffer.find('\n', last_line_pos + 1)
                self.terminal.write(self.buffer[last_line_pos+1:last_line_end])

            self.reset_scrolling_region()
            self.terminal.restoreCursor()

            old_bol, old_eol = self.bol_pos(), self.eol_pos()
            self.goto_prev_line()

            go_forward = self.eol_pos() - self.bol_pos()
            if go_forward:
                self.terminal.cursorForward(go_forward)
            self.terminal.write(self.buffer[old_bol:old_eol])
            self.terminal.cursorPos.x += old_eol - old_bol

            go_backward = old_eol - old_bol
            if go_backward:
                self.terminal.cursorBackward(go_backward)
            self.buffer = self.buffer[:old_bol - 1] + self.buffer[old_bol:]

            self.current_column += go_forward
            self.pos += go_forward
            self.lines -= 1

            return

        self.terminal.cursorBackward()
        self.terminal.deleteCharacter()
        self.pos -= 1
        self.current_column -= 1
        self.delete_character()

    def handle_BEGIN_LINE(self):
        move_backward = self.pos - self.bol_pos()
        self.current_column = 0
        if move_backward:
            self.pos = self.bol_pos()
            self.terminal.cursorBackward(move_backward)

    def handle_END_LINE(self):
        move_forward = self.eol_pos() - self.pos
        self.current_column = max(0, self.eol_pos() - self.bol_pos())
        if move_forward:
            self.pos = self.eol_pos()
            self.terminal.cursorForward(move_forward)

    def handle_KILL_LINE(self):
        line_length = max(0, self.eol_pos() - self.bol_pos())
        if line_length:
            self.terminal.eraseToLineEnd()

            eol = self.eol_pos()
            self.buffer = self.buffer[:self.pos] + self.buffer[eol:]
        else:
            # it's equivalent as handling backspace
            self.handle_BACKSPACE()
            # except that we remain at the beginning
            self.handle_BEGIN_LINE()
            # of on this line
            self.goto_next_line()

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

            self.current_column = go_forward

            # twisted insults cannot move by 0 amount
            if go_forward:
                self.terminal.cursorForward(go_forward)
                self.pos += go_forward
        else:
            self.terminal.cursorBackward()
            self.pos -= 1
            self.current_column -= 1

    def handle_RIGHT(self):
        if self.pos >= len(self.buffer):
            return

        if self.char_at(self.pos) == '\n':
            go_back = self.pos - self.bol_pos()
            self.goto_next_line()

            self.current_column = 0

            # twisted insults cannot move by 0 amount
            if go_back:
                self.terminal.cursorBackward(go_back)
        else:
            self.pos += 1
            self.terminal.cursorForward()
            self.current_column += 1

    def handle_UP(self):
        # reached the top of the file
        if self.current_line == 0:
            return

        go_forward = self.pos - self.bol_pos()
        self.goto_prev_line()

        self.fixup_for_shorter_line(go_forward)

    def goto_prev_line(self):
        self.current_line = self.current_line - 1

        if self.char_at(self.pos - 1) == '\n':
            self.pos = self.bol_pos(self.pos - 1)
        else:
            self.pos = self.bol_pos(self.bol_pos() - 1)

        should_fill = self.terminal.cursorPos.y == 0

        # move and possibly scroll
        self.terminal.reverseIndex()

        if should_fill:
            self.terminal.saveCursor()
            self.terminal.cursorHome()
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
        self.current_column -= move_backward

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
            if self.terminal.cursorPos.x:
                self.terminal.cursorBackward(self.terminal.cursorPos.x)
            self.terminal.write(self.buffer[self.pos:self.eol_pos()])
            self.terminal.restoreCursor()

    def handle_REDRAW(self):
        self.redraw_buffer()

    def show_keys(self, keys, prefix='C-'):
        def show_key(key):
            if not isinstance(key, str):
                return str(key)
            if ord(key) == 127:
                return '^H'
            if ord(key) < 32 and key != '\r':
                return prefix + chr(ord('A') + ord(key) - 1)
            return key
        return "-".join(show_key(key) for key in keys)

    def insert_character(self, ch):
        import string
        if not ch in string.printable:
            return

        self.dirty = True

        if ch == '\n':
            self.terminal.eraseToLineEnd()
            self.terminal.saveCursor()

            if self.terminal.cursorPos.y < self.terminal.termSize.y - 1:
                # scroll up part below deleted line
                # XXX: consider using termSize.y instead of computing view size using MODELINE_HEIGHT
                current_screen_line = self.terminal.cursorPos.y
                self.terminal.setScrollRegion(current_screen_line + 2, self.parent.height - self.MODELINE_HEIGHT)
                self.terminal.cursorPosition(0, current_screen_line +  1)
                self.terminal.reverseIndex()

                self.terminal.write(self.buffer[self.pos:self.eol_pos()])
                self.reset_scrolling_region()
                self.terminal.restoreCursor()

                self.terminal.cursorPosition(0, current_screen_line +  1)
            else:
                self.terminal.saveCursor()
                self.terminal.index()
                self.terminal.write(self.buffer[self.pos:self.eol_pos()])
                self.terminal.restoreCursor()

            self.lines += 1
            self.current_line += 1
            self.current_column = 0
            self.terminal.cursorPos.y += 1
            self.terminal.cursorPos.y = min(self.terminal.cursorPos.y, self.terminal.termSize.y - 1)
        else:
            self.current_column += 1

            self.terminal.write(ch)
            # insults doesn't keep track of cursor movement made by write
            self.terminal.cursorPos.x += 1

        self.buffer = self.buffer[:self.pos] + ch + self.buffer[self.pos:]

        self.pos += 1


    def delete_character(self):
        self.buffer = self.buffer[:self.pos] + self.buffer[self.pos+1:]

    def _echo(self, keyID, mod):
        """Echoes characters on terminal like on unix (special chars etc)"""
        if isinstance(keyID, str):
            if keyID in ('\r'):
                keyID = '\n'

            self.insert_character(keyID)

        else:
            log.msg("GOT Special char '%s' (%s)" % (keyID, type(keyID)))

    @exception_logger
    def keystrokeReceived(self, keyID, mod):
        self.trace_keystroke(keyID, mod)

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

        self.refresh_modline()

        if self.tracing and not self.has_quit:
            self.handle_WHAT_CURSOR_POSITION()

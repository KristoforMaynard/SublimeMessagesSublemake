from __future__ import print_function

import os.path
import string
import re
import sublime
from collections import OrderedDict
from operator import attrgetter

from Default import exec

try:
    from SublimeMessages import message_manager
except ImportError:
    from Messages import message_manager

def plugin_loaded():
    global build_msg_src
    build_msg_src = BuildMessageSource()
    message_manager.message_manager.add_source(build_msg_src, 1)

def plugin_unloaded():
    try:
        global build_msg_src
        message_manager.message_manager.del_source(build_msg_src)
        del build_msg_src
    except NameError:
        pass


class BuildMessageSource(message_manager.LineMessageSource):
    # order indicates severity / preference of icon when > 1 err on a line
    pth = "Packages/SublimeMessagesSublemake/x.png"
    markers = OrderedDict([("info", (pth, "sublemake_mark.info")),
                           ("warning", (pth, "sublemake_mark.warning")),
                           ("error", (pth, "sublemake_mark.error"))])
    prefix = "Sublemake"
    pretty_prefix = "Build"

    def parse_errors(self, window, output_view, extra=None, root_dir=None):
        if root_dir is None:
            root_dir = os.getcwd()
        self.clear_window(window)

        window_container = {}
        # first entry in self.markers, least severe
        min_sev = list(self.markers.keys())[0]

        # fill err_list from output_view.find_all_results
        for fname, line, col in output_view.find_all_results():
            abs_fname = fname
            if not abs_fname in window_container:
                window_container[abs_fname] = message_manager.FileInfoDict()
            err_info = message_manager.ErrorInfo(self, line, min_sev, None, False)
            if line not in window_container[abs_fname]:
                window_container[abs_fname][line] = []
            window_container[abs_fname][line].append(err_info)
            # ... i totally forgot what i was gunna put here, but i know
            # i'm missing something... right here ... (reordering?)

        # extra info contains severity and message...
        # change those errinfo instances
        if extra is not None:
            for fname, line, severity, message in extra:
                abs_fname = os.path.normpath(os.path.join(root_dir, fname))
                if not abs_fname in window_container:
                    window_container[abs_fname] = message_manager.FileInfoDict()

                # clobber any pre-existing err_info lists
                if not (line in window_container[abs_fname] and \
                        window_container[abs_fname][line][0].extra):
                    window_container[abs_fname][line] = []

                if severity is None:
                    severity = min_sev
                err_info = message_manager.ErrorInfo(self, line, severity,
                                                 message, True)
                window_container[abs_fname][line].append(err_info)
                window_container[abs_fname][line].sort(key=attrgetter("order"),
                                                       reverse=True)

        # reorder errinfos in each list to maintain priority order


        self.messages[window.id()] = window_container

        # now mark errors in all open views
        for open_view in window.views():
            self.mark_errors(window, open_view)

    def run(self, view):
        raise NotImplementedError("The entry point for this source is "
                                  "'parse_errors', which is called from "
                                  "ExecCommand on bulid")


# class sublemakeCommand(exec.ExecCommand):
class ExecCommand(exec.ExecCommand):
    _show_dir_opt = "-w"

    enter_re = None
    leave_re = None
    err_re = None
    # err_extra_re = None

    root = None
    cdir = None
    broken_line = None

    make = None
    err_extra = None
    extra_err_parse = None


    def run(self, **kwargs):
        # print("EXEC")
        self.cdir = ""
        self.broken_line = None
        self.root = None
        self.make = None
        self.err_extra = None
        env_xparse = kwargs.get("env", {}).get("extra_err_parse", None)
        self.extra_err_parse = (kwargs.pop("extra_err_parse", False) or
                                (env_xparse == "true"))

        build_msg_src.clear_window(self.window)
        # self.window.run_command("clear_build_errors")

        if kwargs.get("kill", False):
            if self.proc:
                self.proc.kill()
                self.proc = None
                self.append_string(None, "[Cancelled]\n")
            return

        shell_cmd = kwargs.get("shell_cmd", None)
        cmd = kwargs.get("cmd", None)

        if isinstance(cmd, str):
            cmd = [cmd]

        # if using make, prep the special sauce
        if (shell_cmd and shell_cmd.startswith("make")) or \
           (cmd and cmd[0].startswith("make")):
            self.make = True
            self.extra_err_parse = True

            if shell_cmd:
                if not self._show_dir_opt in shell_cmd:
                    shell_cmd = "make " + self._show_dir_opt + shell_cmd[4:]
                    kwargs["shell_cmd"] = shell_cmd
            else:
                if not self._show_dir_opt in " ".join(cmd):
                    cmd[0] = "make " + self._show_dir_opt + cmd[0][4:]
                    kwargs["cmd"] = cmd
        else:
            self.make = False

        if self.extra_err_parse:
            if self.enter_re == None:
                enter_str = r"make(?:\[[0-9]+\])?: Entering directory\s+`(.*)'"
                self.enter_re = re.compile(enter_str)
            if self.leave_re == None:
                leave_str = r"make(?:\[[0-9]+\])?: Leaving directory\s+`(.*)'"
                self.leave_re = re.compile(leave_str)
            if self.err_re == None:
                # err_str = r"(..[^:\n]*):([0-9]+:?[0-9]+?:? .*)$"
                err_str = r"(..[^:\n]*):(([0-9]+):?[0-9]+?:? (.*?:)?(.*))$"
                # err_str = r"(..[^:\n]*):([0-9]+:?[0-9]+?:? (.*))$"
                self.err_re = re.compile(err_str)
                # if self.err_extra_re == None:
                #     err_extra_str = r"(..[^:\n]*):([0-9]+:)?([0-9]+?:)?\s*(.*)$"
                #     self.err_extra_re = re.compile(err_extra_re)
            self.err_extra = []

        super(ExecCommand, self).run(**kwargs)
        # super().run(**kwargs)

        self.root = self.output_view.settings().get("result_base_dir")

    def append_data(self, proc, data):
        if self.extra_err_parse:
            try:
                data_str = data.decode(self.encoding)
                data_arr = []
                for line in data_str.splitlines(keepends=True):
                    if not line.endswith(('\n', '\r')):
                        if self.broken_line is None:
                            self.broken_line = line
                        else:
                            self.broken_line += line
                        continue

                    if self.broken_line is not None:
                        line = self.broken_line + line
                        self.broken_line = None
                    err = re.match(self.err_re, line)
                    if err:
                        fname = os.path.join(self.cdir, err.group(1))
                        data_arr.append("{0}:{1}\n".format(fname, err.group(2)))
                        # fill the extra info
                        if err.group(5) is not None:
                            line = int(err.group(3))
                            sev = err.group(4).lower().strip(" :")
                            msg = err.group(5)
                            self.err_extra.append((fname, line, sev, msg))
                        continue

                    enter = re.match(self.enter_re, line)
                    if enter:
                        self.cdir = os.path.relpath(enter.group(1), self.root)
                        continue

                    leave = re.match(self.leave_re, line)
                    if leave:
                        pass
                        continue
                    data_arr.append("{0}".format(line))

                data = ("".join(data_arr)).encode(self.encoding)
            except Exception as e:
                pass
                print("Oops: ", e)

        super(ExecCommand, self).append_data(proc, data)
        # super().append_data(proc, data)

    def finish(self, proc):
        if self.broken_line is not None:
            self.append_data(proc, "\n".encode())
        super(ExecCommand, self).finish(proc)
        # super().finish(proc)
        if self.broken_line is not None:
            self.append_data(proc, "\n".encode())

        build_msg_src.parse_errors(self.window, self.output_view,
                                   extra=self.err_extra,
                                   root_dir=self.root)
        self.err_extra = None
        self.cdir = None
        self.root = None
        self.make = None
        self.extra_err_parse = None

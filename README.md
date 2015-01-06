SublimeMessagesSublemake
========================

Better compile error feedback for Sublime Text.

This plugin addresses two shortcomings of the ST build system when it comes to building makefiles:

 + ST does not understand recursive makefile builds. It opens the wrong file on build errors because it does not parse "Entering directory" lines like Vim and Emacs do.
 + Build errors are not marked in the gutter.

This plugin gets automatically called on build, and if the build command is "make", it will correctly handle recursive builds. After the build is complete, lines with errors or warnings will be marked in the gutter. Gutter marks can be cleared with the "Sublemake: Clear Errors (...)" commands, accessible in the command pallet.

Prerequisits:
-------------

 - [SublimeMessages] plugin

How it works:
-------------

All build output is passed through this plugin, so it is enabled automatically.

[SublimeMessages]: https://github.com/KristoforMaynard/SublimeMessages

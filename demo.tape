# ContextOS demo tape — renders demo/demo.gif

Output demo/demo.gif

Set Shell "bash"
Set FontSize 14
Set Width 900
Set Height 550
Set Theme "Dracula"
Set Padding 20
Set Margin 10
Set BorderRadius 8
Set TypingSpeed 35ms

Hide
Type "source /Users/rohithmatam/ContextOS/.venv/bin/activate && cd /tmp/contextos-demo-run"
Enter
Sleep 500ms
Show

Sleep 500ms

Type "contextos init"
Enter
Sleep 2s

Type "contextos scan ."
Enter
Sleep 3s

Type "contextos task 'fix auth bug: token expiry not validated on refresh'"
Enter
Sleep 1s

Type "contextos pack . --task 'fix auth bug' --budget 4000"
Enter
Sleep 3s

Type "contextos export claude --repo . --task 'fix auth bug'"
Enter
Sleep 2s

Type "head -30 .contextos/CLAUDE_CONTEXT.md"
Enter
Sleep 4s

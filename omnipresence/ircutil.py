"""IRC-specific utility functions."""
import re

# Common IRC formatting control codes
# <http://forum.egghelp.org/viewtopic.php?p=94834>
# <http://www.mirc.com/help/colors.html>
CONTROL_CODES = re.compile(r"""
(
  \x02              # Bold
  |
  \x03(             # Color
    [0-9]?[0-9](    # Optional foreground number (from 0 or 00 to 99)
      ,[0-9]?[0-9]  # Optional background number (from 0 or 00 to 99)
    )?
  )?
  |
  \x0F              # Normal (revert to default formatting)
  |
  \x16              # Reverse video (sometimes rendered as italics)
  |
  \x1F              # Underline
)
""", re.VERBOSE)


def canonicalize(name):
    """Convert an IRC name to its "canonical" lowercase representation."""
    return name.lower().replace('[',  '{').replace(']',  '}') \
                       .replace('\\', '|').replace('^',  '~')

def remove_control_codes(s):
    """Remove IRC formatting control codes from a string."""
    return CONTROL_CODES.sub('', s)
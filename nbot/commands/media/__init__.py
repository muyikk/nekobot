"""Media subpackage."""
from nbot.commands.media.image import (
    handle_random_image,
    handle_random_emoticons,
    handle_st,
    handle_loli,
    handle_r18,
)
from nbot.commands.media.video import (
    handle_random_video,
    handle_d,
    handle_di,
    handle_df,
)
from nbot.commands.media.music import handle_music, handle_random_music
from nbot.commands.media.dice_rps import handle_random_dice, handle_random_rps

__all__ = [
    "handle_random_image",
    "handle_random_emoticons",
    "handle_st",
    "handle_loli",
    "handle_r18",
    "handle_random_video",
    "handle_d",
    "handle_di",
    "handle_df",
    "handle_music",
    "handle_random_music",
    "handle_random_dice",
    "handle_random_rps",
]

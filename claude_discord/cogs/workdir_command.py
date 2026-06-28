"""``/cd`` and ``/cdnew`` slash commands — pick a working directory via autocomplete.

- ``/cd <path>`` retargets the **current** thread to a folder. Claude Code ties a
  session to the folder it started in, so this starts a *fresh* session in the new
  folder (same Discord thread) — the prior conversation can't carry across.
- ``/cdnew <path>`` opens a **new** thread bound to a folder; the first message in
  it starts a session there.

Directories are discovered under the configured project roots
(``CCDB_PROJECT_ROOTS``, default ``~/Developer``) and offered via Discord
autocomplete, so you never need the full path string.
"""

from __future__ import annotations

import logging
from pathlib import Path

import discord
from discord import app_commands
from discord.ext import commands

from ..database.repository import SessionRepository
from ..workdir import display_label, find_directories, resolve_project_roots

logger = logging.getLogger(__name__)


class WorkdirCommandCog(commands.Cog):
    """Exposes /cd and /cdnew for choosing a session's working directory."""

    def __init__(
        self,
        bot: commands.Bot,
        repo: SessionRepository,
        claude_channel_id: int,
        *,
        allowed_user_ids: set[int] | None = None,
        claude_channel_ids: set[int] | None = None,
        project_roots: list[Path] | None = None,
    ) -> None:
        self.bot = bot
        self.repo = repo
        self.claude_channel_id = claude_channel_id
        self._allowed_user_ids = allowed_user_ids
        self._channel_ids: set[int] = claude_channel_ids or {claude_channel_id}
        # When None, roots are resolved live from CCDB_PROJECT_ROOTS on each call.
        self._project_roots = project_roots

    # -- helpers -------------------------------------------------------------

    def _roots(self) -> list[Path]:
        if self._project_roots is not None:
            return self._project_roots
        return resolve_project_roots()

    def _is_authorized(self, user_id: int) -> bool:
        return self._allowed_user_ids is None or user_id in self._allowed_user_ids

    def _is_claude_thread(self, channel: object) -> bool:
        return isinstance(channel, discord.Thread) and channel.parent_id in self._channel_ids

    @staticmethod
    def _validate_dir(value: str) -> Path | None:
        try:
            path = Path(value).expanduser()
        except (OSError, ValueError):
            return None
        return path if path.is_dir() else None

    async def _path_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Return up to 25 matching directories for autocomplete."""
        dirs = find_directories(self._roots(), current or "")
        return [app_commands.Choice(name=display_label(d)[:100], value=str(d)) for d in dirs]

    # -- /cd -----------------------------------------------------------------

    @app_commands.command(
        name="cd",
        description="Retarget THIS thread to a folder (starts a fresh session there)",
    )
    @app_commands.describe(path="Folder to run this thread in (type to filter)")
    @app_commands.autocomplete(path=_path_autocomplete)
    async def cd(self, interaction: discord.Interaction, path: str) -> None:
        if not self._is_authorized(interaction.user.id):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return
        if not self._is_claude_thread(interaction.channel):
            await interaction.response.send_message(
                "Use `/cd` inside a Claude thread. To start a new session in a "
                "folder, use `/cdnew`.",
                ephemeral=True,
            )
            return
        directory = self._validate_dir(path)
        if directory is None:
            await interaction.response.send_message(f"Not a directory: `{path}`", ephemeral=True)
            return
        # Empty session_id forces a fresh session next message; Claude ties a
        # session to its folder, so the old one can't be resumed elsewhere.
        await self.repo.save(interaction.channel.id, "", working_dir=str(directory))
        await interaction.response.send_message(
            f"📂 This thread now targets `{directory}`.\n"
            "Your next message starts a **fresh session** there."
        )

    # -- /cdnew --------------------------------------------------------------

    @app_commands.command(name="cdnew", description="Open a NEW session in a folder")
    @app_commands.describe(path="Folder for the new session (type to filter)")
    @app_commands.autocomplete(path=_path_autocomplete)
    async def cdnew(self, interaction: discord.Interaction, path: str) -> None:
        if not self._is_authorized(interaction.user.id):
            await interaction.response.send_message("Not authorized.", ephemeral=True)
            return
        directory = self._validate_dir(path)
        if directory is None:
            await interaction.response.send_message(f"Not a directory: `{path}`", ephemeral=True)
            return

        invoke_ch = interaction.channel
        if isinstance(invoke_ch, discord.TextChannel) and invoke_ch.id in self._channel_ids:
            channel = invoke_ch
        else:
            channel = self.bot.get_channel(self.claude_channel_id)
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Claude channel not found.", ephemeral=True)
            return

        thread = await channel.create_thread(
            name=f"📂 {directory.name}"[:100],
            type=discord.ChannelType.public_thread,
        )
        # Pre-seed the working dir (empty session_id → fresh session on first message).
        await self.repo.save(thread.id, "", working_dir=str(directory))
        await interaction.response.send_message(
            f"🆕 New session in `{directory}` → {thread.mention}\n"
            "Send your first message in that thread to begin."
        )

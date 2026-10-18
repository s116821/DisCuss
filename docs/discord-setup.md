# Discord application setup and permissions

Complete this once for each separately authorized bot identity. DisCuss runs as a server-installed bot; a user-only installation does not supply a voice listener.

## Developer Portal installation settings

1. Open your application in the [Discord Developer Portal](https://discord.com/developers/applications). On **Bot**, use its bot token in the protected local config. If a new token is needed, **Reset Token** generates it; resetting invalidates the previous token. The OAuth client secret and public key are not bot tokens. Never put the token in a URL, command argument, issue or chat.
2. Open **Installation**, enable **Guild Install**, and select **Discord Provided Link** for the install link. Under **Default Install Settings → Guild Install**, select the `bot` and `applications.commands` scopes.
3. In that section's bot **Permissions** menu, request the permissions below. Include **Speak** when enabling voice playback; receiving voice alone does not require it.
4. Save, then use the install link and choose **Add to server** for the intended server. The installing account needs permission to manage that server.
5. Verify the installed bot role and category/channel overrides in Discord. Updating portal defaults alone is not proof that an existing installation has the required effective permissions. For an existing bot, update its server permissions or authorize the updated install link, then check the channels again. Administrator permission is unnecessary.

Portal navigation follows [Discord's installation guide](https://docs.discord.com/developers/quick-start/getting-started#adding-scopes-and-bot-permissions); effective access follows [Discord's permission and overwrite rules](https://docs.discord.com/developers/topics/permissions). DisCuss does not require privileged Message Content or Server Members intents. Configure `primary_bot` explicitly; the primary identity owns commands, announcements and text reports.

## Channel access

| Function | Required access |
| --- | --- |
| Voice reception, for each listener | View Channel and Connect in eligible ordinary voice channels |
| Voice playback | Speak in the capture channel; check Use Voice Activity and mute restrictions if playback is blocked |
| Primary notice, detection reports and scheduled leaderboards | View Channel and Send Messages in each configured text destination |
| `/discuss quotes` history lookup | View Channel and Read Message History for both the primary bot and requester in the detection-report channel |

Private categories and individual channels can override server-role permissions. Check every intended voice channel and each separate text destination. Head Hunt can discover all accessible ordinary voice channels with `head_hunt.all_channels=true`; one bot identity still listens in only one selected channel per server at a time. Stage channels are outside that scope.

The primary processing notice uses `servers[].report_channel_id`. Detection quotes use that channel unless `detection_reporting.channel_id` overrides it. Scheduled leaderboards independently use `leaderboards.report_channel_id`, or the base channel when unset. See the [split-channel configuration example](configuration.md#separate-quotes-and-leaderboards).

## A bot appears muted or replays are silent

Check server mute, self-mute, effective Speak permission and Discord's `suppress` voice-state flag. [Discord defines these separately](https://docs.discord.com/developers/resources/voice#voice-state-object): permission being allowed does not establish that the active connection is unsuppressed. If permissions changed while the bot was connected, reconnect it through normal application operation and recheck the resulting state. In one operator deployment, suppression was clear after permission updates and reconnection; this does not establish the cause of every mute problem. A user can also mute the bot locally or lower its playback volume.

An enabled playback cycle is not a continuous recording or an immediate sound test. Only a qualifying curse clip from the selected person can supply that cycle; no acquired clip means no replay. The replay must remain in its original channel. Use `/discuss status` or the metadata-only local health snapshot to inspect readiness, playback attempts and failures. Do not inject test audio into a community server; acceptance testing belongs in an explicitly authorized disposable server.

## Applying settings on an installed host

Follow the [native installation guide](https://github.com/s116821/DisCuss/blob/main/deploy/INSTALL.md) for boot startup and private storage. Windows installation and edits under protected `ProgramData` require an elevated PowerShell/UAC approval; an ordinary-user test config in a private folder does not inherently require administrator rights.

For policy changes, validate a protected candidate with `discuss --config PATH doctor` before replacing the active config. Preserve its private ACLs and every unrelated setting, including credentials. Destination and playback-interval changes reload in the same application process, briefly release/reconnect voice and clear pending excerpts and captured replay clips. Identity, token, model or state-directory changes require a restart. See [policy edits](configuration.md#editing-a-running-installation). Publishing a new release does not upgrade the installed runtime; a code update uses the verified native installer.

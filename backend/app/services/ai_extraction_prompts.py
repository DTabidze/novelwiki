BASE_EXTRACTION_SYSTEM_PROMPT = """
You extract structured wiki-style information from Asian cultivation and LitRPG novel chapters.

Return ONLY valid JSON.
Use only facts directly supported by the provided chapter text.
Use short evidence snippets. Do not include full chapter text.
If a category has no clear entries, return an empty list.

Primary MVP goal:
- character identity
- aliases
- confirmed character progression
- important skills/items
- character-skill relationships
- hard life-status changes

Timeline events are disabled for now.
Always return "events": [].
Do not put cultivation breakthroughs, rank changes, deaths, fake deaths, resurrections,
body/soul changes, item acquisitions, skill acquisitions, location arrivals, or battles in events.

Use the known wiki memory provided in the user message:
- Use canonical names from memory when a chapter uses a known alias.
- Do not create duplicate entities for known aliases.
- Do not infer two characters are the same unless the chapter or memory strongly supports it.
- Do not output known characters, skills, or items when they are merely mentioned again.
- Output known entities only when this chapter adds durable new wiki information.

GENERAL RULES:
- Never invent facts.
- Preserve the chapter's exact terminology for realms, ranks, skills, items, sects, and titles.
- Evidence must directly support the exact extracted fact.
- Do not attach evidence about one character, item, skill, or event to another.
- Prefer "unknown" or an empty field over guessing.

CHARACTERS:
Extract named characters and distinctive recurring unnamed characters.

Extract a character if they:
- are physically present, speak, act, fight, teach, capture, rescue, attack, distribute resources, or drive the scene
- are important titled/role-named figures, even if their full name is not revealed yet
- have a stable recurring descriptive label, such as "Fat Teenager", "Horse-faced Young Man", "Green-robed Man", "Elder Sister Xu", "Brother Chen", or "Master Uncle Shangguan"

Skip:
- generic background people
- unnamed groups
- numbered placeholders
- ordinary labels like "a servant", "one disciple", "a guard", "the young man", "the woman"

Do not create group characters such as "cultivation monks", "guards", "disciples", or "servants".
Extract individuals only.

appearance_type:
- Use "appeared" only when the character is physically present, speaks, acts, or directly participates.
- Use "mentioned" when the character is only named, remembered, referenced, or discussed.
- In the examples below, X means any character name or alias. Do not treat X as a literal character name.
- Mark "appeared" when the text confirms current-scene physical presence, even if the character does not speak, fight, or perform a major action yet.
- Current-scene arrival/presence wording counts as appeared. Examples: "X is here", "X has arrived", "X came", "X entered", "X appeared", "X stood nearby", "X was among the crowd", "X sat nearby", "X watched from the side", "Look, X is here", or "Someone shouted that X had arrived".
- Do not mark "appeared" for absence, rumor, memory, historical reference, future possibility, or comparison wording. Examples: "X isn't here", "Too bad X isn't here", "People say X is strong", "X once did...", "If X comes later", or "X might appear".

CHARACTER METADATA:
Extract durable character metadata only when clearly stated in the chapter text.

Metadata can include:
- age or approximate age
- gender
- race/species
- origin, home, or place of birth
- faction, sect, clan, or organization affiliation
- life status only: alive, dead, historical, missing, sealed, reincarnated, or unknown
- titles or stable roles

Do not guess metadata.
Do not infer metadata from stereotypes.
Do not extract temporary moods, temporary injuries, temporary locations, or temporary possessions as metadata.
Do not put sect roles, occupations, disciple ranks, social positions, titles, or faction roles in status.
Use faction_or_affiliation for sect/clan/organization membership.
Use titles for stable titles or roles.
Only extract status when there is a meaningful life-status change or special condition.
Do not extract status="alive" merely because a character appears, speaks, fights, or acts.
Only extract status="dead" when death is explicit, such as "he died", "she was killed", "his corpse", "her soul dispersed", or clear confirmed death narration.
Use status="historical" only for ancient, legendary, or past-era figures referenced but not appearing in the current timeline.
Use exact wording when possible.
If metadata is not clearly stated, use null or an empty titles list.
If metadata already exists in memory, do not repeat it unless this chapter provides a clearer or more current durable fact.

ALIASES:
- Include alternate labels used in this chapter: titles, nicknames, partial names, descriptive labels.
- Do not include the canonical name as an alias.
- When a real name is revealed, use the real name as canonical and put the old title/label in aliases.
- Only add an alias when the chapter clearly uses that alias for the same character.

Canonical name priority:
1. Full real name. Examples: Li Furui, Xu Qing, Meng Hao.
2. Stable sect/title name. Examples: Elder Sister Xu, Cultivator Shangguan, Brother Chen, Founder Reliance.
3. Stable nickname or recurring label. Examples: Fatty, Fat Teenager, Horse-faced Young Man.
4. Honorific-only or localized forms. Examples: Ms. Xu, Mr. Shangguan, Sister Xu.
5. Generic visual descriptions. Examples: pale-faced woman, silver robe woman, green-robed man.

Use the highest-priority name clearly supported by the chapter or memory.
If a full real name exists, use it as canonical.
If no full real name exists, prefer a stable title-style name over honorific-only forms.
Example: use "Elder Sister Xu" instead of "Ms. Xu".
If no real name or title-style name exists, use a stable nickname or recurring label.
Example: use "Fatty" or "Fat Teenager" if that is the only stable label.
Do not use generic visual descriptions as canonical unless no better stable name exists.
Put lower-priority labels used for the same character into aliases.
If a real name is revealed later, use the real name as canonical and keep old labels as aliases.

PROGRESSION:
Any confirmed cultivation, power, realm, rank, stage, layer, grade, class, job, position, title, disciple status, promotion, or breakthrough belongs in progression_events.

A progression_event is required when the chapter confirms:
- a breakthrough, advancement, promotion, rank-up, class/job change, or position change happened
- a current cultivation/power level, realm, stage, rank, layer, grade, position, class, job, title, or status is stated for the first time
- a level/rank is stated after training, meditation, pill/resource use, battle, recovery, awakening, or breakthrough context

Do NOT save progression_events for:
- near breakthroughs
- plans, hopes, requirements, guesses, instructions, or future possibilities
- unchanged "still/remains" statements
- repeated known values from memory
- item rewards, gifts, purchases, resources, or temporary possessions

CONFIRMED VS FUTURE PROGRESSION:
Only output progression_events for:
- confirmed current states
- confirmed breakthroughs
- confirmed promotions
- confirmed durable status changes

Do NOT output progression_events for:
- future possibilities
- predictions
- estimates
- plans
- hopes
- intentions
- requirements
- near-breakthroughs
- conditional statements
- internal speculation

Important:
A realm/level mention alone is NOT sufficient.

The text must clearly indicate the character already:
- reached
- entered
- advanced to
- broke through to
- became
- currently is at
- currently possesses
that level/status.

Strong negative indicators include phrases such as:
- can reach
- could reach
- might reach
- maybe
- perhaps
- almost
- close to
- nearly
- with more
- need more
- if I
- should be able to
- would be able to
- I think
- I believe
- soon
- not yet
- preparing to
- attempting to

Example:
"I think with three or maybe five more, I can reach the third level of Qi Condensation."
=> NOT a progression_event.

Example:
"His cultivation foundation was at the third level of Qi Condensation."
=> confirmed progression fact.

IMPORTANT CLARIFICATION:
A short exclamation or realization CAN be confirmed progression if nearby context clearly shows the level/status was already reached.

Example:
"The third level of Qi Condensation!"
after consuming cultivation resources and successfully advancing
=> confirmed progression fact.

But:
"just a hair away from being at the peak of the third level"
=> NOT peak third level progression.
This is near-progression and should not be saved as a confirmed progression_event.

Important distinction:
- speculation about reaching a level later = NOT progression
- confirmed possession of a level now = progression

CONFIRMED PROGRESSION VS LATER NEAR-PROGRESSION:
If the text first confirms that a character reached, advanced to, became, entered, unlocked, achieved, or currently possesses a level/rank/stage/status, extract that confirmed progression_event.

If a later sentence says the character is close to, almost at, near, just short of, approaching, preparing for, or not far from a higher/next/peak level/rank/stage/status, do NOT let that later near-progression wording cancel the earlier confirmed progression.

Extract:
- the confirmed reached/current level/rank/stage/status

Do NOT extract:
- the later near/almost/close-to higher level/rank/stage/status

Reason:
A confirmed current state and a near-future/near-next state are different facts. The confirmed current state should be saved. The near-next state should not be saved as confirmed progression.

Generic example:
"The third rank!"
followed by:
"he was just short of the peak of the third rank"

=> extract:
new_value: "third rank"

=> do NOT extract:
new_value: "peak of the third rank"

Generic example:
"She unlocked Level 20."
followed by:
"she was already close to Level 21"

=> extract:
new_value: "Level 20"

=> do NOT extract:
new_value: "Level 21"

PROGRESSION ATTRIBUTION:
When extracting a progression_event, attach the progression only to the character who is explicitly stated or clearly implied to possess or reach that level/status.

Do not attach the same progression fact to multiple characters unless the text clearly supports multiple characters having that progression.

A progression_event must be directly supported by evidence for that specific character.

If the owner of the progression is unclear or ambiguous:
- prefer the explicitly named subject
- otherwise use the strongest directly-supported subject
- do not guess

Do not copy one character's cultivation/rank/status onto another character without direct textual support.

Progression extraction is mandatory.
If any character description, skill description, character_skill entry, or evidence snippet mentions a confirmed level/rank/status, there must be a matching progression_event.

LIFE EVENTS:
life_events are only for hard status changes:
- death
- fake_death
- resurrection
- body_destroyed
- soul_survived
- sealed

Do not create life_events for:
- injury
- fear
- being trapped
- being captured
- being rescued
- confusion
- uncertain future
- temporary danger

SKILLS:
Skills are named techniques, spells, abilities, martial arts, cultivation methods, divine abilities, classes abilities, or combat moves.

Extract a skill if it is:
- learned
- known
- used
- mastered
- created
- taught
- explained as important
- newly named

Do not put manuals, pills, artifacts, medicines, treasures, resources, scrolls, or physical objects in skills.
A manual or scroll is an item. Only a named technique inside it is a skill.

CHARACTER_SKILLS:
Output one character_skills entry when a character clearly has a named skill because they:
- learns
- uses
- knows
- masters
- creates
- teaches
a named skill.

If a character_skills entry references a skill not already listed in memory, also output that skill in skills.
Set relationship_type to "has".
Do not repeat a known character-skill relationship from memory. Different action verbs do not create different relationships.

ITEMS:
Items must be wiki-significant.

Extract:
- artifacts
- weapons
- cultivation manuals
- technique scrolls/manuals
- pills
- medicines
- treasures
- named quest items
- unique equipment
- recurring plot-critical objects

Skip:
- ordinary clothing
- uniforms
- servant robes
- food
- furniture
- rooms
- buildings
- generic tools
- common supplies
- ordinary jade slips
- direction slips
- administrative paperwork
- badges/passes/tokens unless magical, named, recurring, or plot-critical

Do not extract places, sects, mountains, caves, pavilions, resources, manuals, or items as characters.

FINAL CHECK BEFORE JSON:
1. Resolve aliases inside the chapter.
2. Use canonical names from memory when supported.
3. Check every character for confirmed cultivation/power/rank/status changes.
4. Check every skill and character_skill description for hidden progression facts.
5. Make sure all confirmed progression facts have matching progression_events.
6. Make sure events is always [].
7. Make sure all evidence snippets are short and directly relevant.
"""

PROGRESSION_AUDIT_PROMPT = """
You perform a second-pass audit focused ONLY on character power progression.

Return ONLY valid JSON containing progression_events.
Do not extract characters, skills, items, character_skills, life_events, locations, or timeline events.

Your job:
Catch every confirmed cultivation, power, realm, rank, stage, layer, grade, class, job, position,
title, disciple status, promotion, or breakthrough in the chapter.

Scan for:
- first/second/third/fourth/fifth/etc. level
- Qi Condensation, Foundation Establishment, Core Formation, Nascent Soul, or any other realm
- cultivation base/foundation/power was...
- has reached...
- achieved...
- broke through...
- advanced to...
- became...
- was promoted to...
- short exclamations like "The third level of Qi Condensation!"

For each confirmed match:
- identify the character from nearby context, active viewpoint, or known memory
- use progression_type "cultivation_level" for realms/levels
- use progression_type "rank" for ranks/grades/layers if not cultivation
- use progression_type "position" for durable title, job, class, sect role, or disciple status
- use the chapter's exact wording in new_value
- include old_value only when explicitly stated nearby
- include short direct evidence
- do not include repeated known values from memory

Output progression_events for:
- confirmed current levels
- confirmed breakthroughs
- confirmed promotions
- confirmed durable status/position/class/job changes

Do NOT output:
- near breakthroughs
- hopes
- plans
- requirements
- guesses
- instructions
- future possibilities
- unchanged "still/remains" statements
- rewards, items, pills, gifts, purchases, or temporary possessions

CONFIRMED VS FUTURE PROGRESSION:
Only output progression_events for:
- confirmed current states
- confirmed breakthroughs
- confirmed promotions
- confirmed durable status changes

Do NOT output progression_events for:
- future possibilities
- predictions
- estimates
- plans
- hopes
- intentions
- requirements
- near-breakthroughs
- conditional statements
- internal speculation

Important:
A realm/level mention alone is NOT sufficient.

The text must clearly indicate the character already:
- reached
- entered
- advanced to
- broke through to
- became
- currently is at
- currently possesses
that level/status.

Strong negative indicators include phrases such as:
- can reach
- could reach
- might reach
- maybe
- perhaps
- almost
- close to
- nearly
- with more
- need more
- if I
- should be able to
- would be able to
- I think
- I believe
- soon
- not yet
- preparing to
- attempting to

Example:
"I think with three or maybe five more, I can reach the third level of Qi Condensation."
=> NOT a progression_event.

Example:
"His cultivation foundation was at the third level of Qi Condensation."
=> confirmed progression fact.

IMPORTANT CLARIFICATION:
A short exclamation or realization CAN be confirmed progression if nearby context clearly shows the level/status was already reached.

Example:
"The third level of Qi Condensation!"
after consuming cultivation resources and successfully advancing
=> confirmed progression fact.

But:
"just a hair away from being at the peak of the third level"
=> NOT peak third level progression.
This is near-progression and should not be saved as a confirmed progression_event.

Important distinction:
- speculation about reaching a level later = NOT progression
- confirmed possession of a level now = progression

CONFIRMED PROGRESSION VS LATER NEAR-PROGRESSION:
If the text first confirms that a character reached, advanced to, became, entered, unlocked, achieved, or currently possesses a level/rank/stage/status, extract that confirmed progression_event.

If a later sentence says the character is close to, almost at, near, just short of, approaching, preparing for, or not far from a higher/next/peak level/rank/stage/status, do NOT let that later near-progression wording cancel the earlier confirmed progression.

Extract:
- the confirmed reached/current level/rank/stage/status

Do NOT extract:
- the later near/almost/close-to higher level/rank/stage/status

Reason:
A confirmed current state and a near-future/near-next state are different facts. The confirmed current state should be saved. The near-next state should not be saved as confirmed progression.

Generic example:
"The third rank!"
followed by:
"he was just short of the peak of the third rank"

=> extract:
new_value: "third rank"

=> do NOT extract:
new_value: "peak of the third rank"

Generic example:
"She unlocked Level 20."
followed by:
"she was already close to Level 21"

=> extract:
new_value: "Level 20"

=> do NOT extract:
new_value: "Level 21"

PROGRESSION ATTRIBUTION:
When extracting a progression_event, attach the progression only to the character who is explicitly stated or clearly implied to possess or reach that level/status.

Do not attach the same progression fact to multiple characters unless the text clearly supports multiple characters having that progression.

A progression_event must be directly supported by evidence for that specific character.

If the owner of the progression is unclear or ambiguous:
- prefer the explicitly named subject
- otherwise use the strongest directly-supported subject
- do not guess

Do not copy one character's cultivation/rank/status onto another character without direct textual support.

Before returning JSON:
- Check if the main extraction missed any progression fact.
- Check short realization/exclamation sentences after training, meditation, pill use, resource use, battle, recovery, or awakening.
- Return only confirmed progression_events.
"""

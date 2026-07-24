BASE_EXTRACTION_SYSTEM_PROMPT = """
You extract structured wiki-style information from Asian cultivation and LitRPG novel chapters.

Return ONLY valid JSON.
Use only facts directly supported by the provided chapter text.
Evidence must be exact raw text copied from the provided chapter. Do not include full chapter text.
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
- Preserve exact terminology inside the correct category. Do not keep a wrong category just because a term is important.
- Evidence must directly prove the exact extracted fact, not merely be nearby, scene-related, or thematically related.
- Do not attach evidence about one character, item, skill, or event to another.
- Prefer "unknown" or an empty field over guessing.

EVIDENCE RULES:
- Return only exact raw text from the provided chapter in every evidence field.
- Evidence must be copied character-for-character from the chapter text as much as possible.
- Do not paraphrase, summarize, normalize, rewrite, translate, correct grammar, change punctuation, change capitalization, add words, remove important words, or interpret the evidence.
- The evidence string must appear in the chapter text.
- Do not explain inside the evidence field.
- Do not replace aliases with canonical names in evidence.
- Do not convert pronouns into names in evidence.
- Do not simplify cultivation states.
- Do not remove uncertainty words like "almost," "as if," "seemed," "would," "might," or "about to."
- Evidence should usually be one sentence.
- If the fact needs two nearby sentences to be supported, use the shortest exact continuous excerpt that supports it.
- Do not stitch together non-contiguous sentences.
- Do not add "..." unless the ellipsis appears in the chapter text.
- If no exact excerpt supports the fact, do not extract that fact.
- The backend verifies evidence against chapter text. Exact raw evidence is required for validation, auto-approval, review, and display.

EVIDENCE QUALITY RULES:
- Evidence must directly prove the candidate fact itself.
- Do not use weak nearby evidence that only mentions the scene, location, movement, owner, item, skill, or character without proving the extracted fact.
- Do not use evidence that would require the reader to accept your explanation outside the evidence field.
- For character identity, evidence should contain the character name, alias, stable label, or clear identifying phrase.
- For items, evidence should directly mention the item and show it as a real physical object.
- For skills, evidence should directly mention the skill/technique/art/ability or clearly describe its use.
- For metadata, evidence must directly support the specific field: age evidence contains age wording; status evidence contains life/death/status wording; faction evidence contains membership/affiliation wording; title evidence contains title/rank/addressing wording; species evidence explicitly communicates species/race.
- For progression, evidence must directly support the exact value and preserve wording such as "peak of the second level" and uncertainty words such as "almost", "seemed", "as if", "would", "might", or "about to".
- For life events, evidence must directly support the hard life-status event. Death evidence must clearly show death, killed, corpse, lifeless, dead, or equivalent direct wording.
- If exact raw evidence does not directly prove the fact, omit the fact.

Examples:
Bad evidence: "Li Furui broke through to the Second Level."
Good evidence: "Fatty broke through to the Second Level."

Bad evidence: "Meng Hao was close to the Third Level."
Good evidence: "He was almost at the Third Level."

Bad relationship evidence:
Fact: a character obtained an item.
Evidence: "He waved his wide sleeve, and a whistling wind picked up the character..."
Reason: scene-related movement does not prove the character obtained the item.

Bad relationship evidence:
Fact: a character lost an item.
Evidence: "Hand over your treasures..."
Reason: a demand or threat does not prove the item was actually lost.

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
- skills, techniques, arts, spells, abilities, items, artifacts, manuals, books, scrolls, or jade slips

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
- learned, acquired, used, or improved skills are NOT progression unless the text confirms a durable class, rank, realm, level, job, position, or state changed

TYPE BOUNDARIES:
- "Were-demon skill", "Flame Serpent Art", "Water Arrow Technique", and similar named skills/arts/techniques are skills, not progression.
- "Bronze Rank", "Level 7", "Foundation Establishment", "Outer Sect disciple", and similar durable ranks/realms/positions are progression.

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
Do not extract cultivation realms, ranks, levels, stages, classes, jobs, positions, titles, or disciple statuses as skills.
Realm/rank/position examples such as "Qi Condensation", "Foundation Establishment", "Bronze Rank", "Level 7", or "Outer Sect disciple" are progression states unless the evidence explicitly describes a method, practice, manual, scripture, or technique being learned.
An artifact or item enabling an action is not a skill.

Boundary examples:
- "Qi Condensation" = realm/progression.
- "Qi Condensation Method" = possible skill/method if evidence describes learning or practicing a method.
- "Qi Condensation Manual" = item/manual.

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
Do not create character_skills entries for items or artifacts, even if the item grants flight, attack, defense, storage, healing, or another effect.
If a character uses a named artifact or physical object, create character_items instead of character_skills.
Only create character_skills when the character personally learns, performs, casts, activates, teaches, knows, or masters a named skill, technique, art, spell, method, or ability.
The evidence must prove the character-skill relationship action. Do not extract a character_skill if the evidence only mentions the skill name nearby.

Examples:
- "Elder Sister Xu used the Wind Pennant to fly" => character_item, not character_skill.
- "Meng Hao used Flame Serpent Art" => character_skill.

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
Do not extract techniques, arts, spells, abilities, methods, or skills as items unless the evidence clearly says they are physical media.
Physical media examples: manual, book, scroll, jade slip, tome, scripture, written record.

Boundary examples:
- "Flame Serpent Art" used, cast, activated, or performed => skill, not item.
- "Flame Serpent Art manual" => item/manual.
- "Water Arrow Technique" => skill.
- "Water Arrow Technique jade slip" => item.

CHARACTER_ITEMS:
Output one character_items entry when a character clearly has a meaningful relationship to a wiki-significant item because they:
- own it
- obtain it
- receive it
- give it
- lose it
- use it in a meaningful way

Allowed relationship_type values:
- owns
- obtained
- used
- lost
- gave
- received

If a character_items entry references an item not already listed in memory, also output that item in items.
Do not create character_items entries for generic possessions, clothing, rooms, paperwork, or ordinary supplies.
Do not repeat a known character-item relationship from memory unless this chapter changes the relationship type or adds durable new information.
If the owner/user is unclear, omit the character_items entry.
The evidence must prove both the character/item attribution and the exact relationship action.
- obtained/received evidence must show the character actually got, took, received, accepted, picked up, acquired, was given, or ended up possessing the specific item.
- gave evidence must show transfer from that character to another.
- used evidence must show actual use, not intent or preparation.
- lost evidence must show the item was actually lost, stolen, destroyed, handed over, taken away, or no longer possessed.
- owns evidence must show clear possession or ownership.
Do not extract the relationship if evidence only mentions the item, shows the item appearing, mentions a demand/threat, describes nearby scene movement, or uses vague possession like "treasures" without naming the specific item.

FINAL CHECK BEFORE JSON:
1. Resolve aliases inside the chapter.
2. Use canonical names from memory when supported.
3. Check every character for confirmed cultivation/power/rank/status changes.
4. Check every skill and character_skill description for hidden progression facts.
5. Make sure all confirmed progression facts have matching progression_events.
6. Make sure events is always [].
7. Make sure all evidence excerpts are exact raw chapter text and directly relevant.
"""

JSON_OUTPUT_RULES = """
Return ONLY valid JSON.
Use only facts directly supported by the provided chapter text.
Evidence must be exact raw text copied from the provided chapter. Do not include full chapter text.
If a category has no clear entries, return an empty list.
"""

MEMORY_RULES = """
Use the known wiki memory provided in the user message:
- Use canonical names from memory when a chapter uses a known alias.
- Do not create duplicate entities for known aliases.
- Do not infer two characters are the same unless the chapter or memory strongly supports it.
- Do not output known characters, skills, or items when they are merely mentioned again.
- Output known entities only when this chapter adds durable new wiki information.
"""

GENERAL_RULES = """
GENERAL RULES:
- Never invent facts.
- Preserve the chapter's exact terminology for realms, ranks, skills, items, sects, and titles.
- Preserve exact terminology inside the correct category. Do not keep a wrong category just because a term is important.
- Evidence must directly support the exact extracted fact.
- Do not attach evidence about one character, item, skill, or event to another.
- Prefer "unknown" or an empty field over guessing.
"""

EVIDENCE_RULES = """
EVIDENCE RULES:
- Return only exact raw text from the provided chapter in every evidence field.
- Evidence must be copied character-for-character from the chapter text as much as possible.
- Do not paraphrase, summarize, normalize, rewrite, translate, correct grammar, change punctuation, change capitalization, add words, remove important words, or interpret the evidence.
- The evidence string must appear in the chapter text.
- Do not explain inside the evidence field.
- Do not replace aliases with canonical names in evidence.
- Do not convert pronouns into names in evidence.
- Do not simplify cultivation states.
- Do not remove uncertainty words like "almost," "as if," "seemed," "would," "might," or "about to."
- Evidence should usually be one sentence.
- If the fact needs two nearby sentences to be supported, use the shortest exact continuous excerpt that supports it.
- Do not stitch together non-contiguous sentences.
- Do not add "..." unless the ellipsis appears in the chapter text.
- If no exact excerpt supports the fact, do not extract that fact.
- The backend verifies evidence against chapter text. Exact raw evidence is required for validation, auto-approval, review, and display.

EVIDENCE QUALITY RULES:
- Evidence must directly prove the candidate fact itself.
- Do not use weak nearby evidence that only mentions the scene, location, movement, owner, item, skill, or character without proving the extracted fact.
- Do not use evidence that would require the reader to accept your explanation outside the evidence field.
- For character identity, evidence should contain the character name, alias, stable label, or clear identifying phrase.
- For items, evidence should directly mention the item and show it as a real physical object.
- For skills, evidence should directly mention the skill/technique/art/ability or clearly describe its use.
- For metadata, evidence must directly support the specific field: age evidence contains age wording; status evidence contains life/death/status wording; faction evidence contains membership/affiliation wording; title evidence contains title/rank/addressing wording; species evidence explicitly communicates species/race.
- For progression, evidence must directly support the exact value and preserve wording such as "peak of the second level" and uncertainty words such as "almost", "seemed", "as if", "would", "might", or "about to".
- For life events, evidence must directly support the hard life-status event. Death evidence must clearly show death, killed, corpse, lifeless, dead, or equivalent direct wording.
- If exact raw evidence does not directly prove the fact, omit the fact.

Examples:
Bad evidence: "Li Furui broke through to the Second Level."
Good evidence: "Fatty broke through to the Second Level."

Bad evidence: "Meng Hao was close to the Third Level."
Good evidence: "He was almost at the Third Level."

Bad evidence: "Meng Hao learned the Qi Condensation Method."
Good evidence: exact sentence from the chapter containing "Qi Condensation Method".

Bad relationship evidence:
Fact: a character obtained an item.
Evidence: "He waved his wide sleeve, and a whistling wind picked up the character..."
Reason: scene-related movement does not prove the character obtained the item.

Bad relationship evidence:
Fact: a character lost an item.
Evidence: "Hand over your treasures..."
Reason: a demand or threat does not prove the item was actually lost.
"""

CHARACTER_RULES = """
CHARACTERS:
Extract named characters and distinctive recurring unnamed characters.

Extract a character if they:
- are physically present, speak, act, fight, teach, capture, rescue, attack, distribute resources, or drive the scene
- are important titled/role-named figures, even if their full name is not revealed yet
- have a stable recurring descriptive label, such as "Fat Teenager", "Horse-faced Young Man", "Green-robed Man", "Elder Sister Xu", "Brother Chen", or "Master Uncle Shangguan"

Skip generic background people, unnamed groups, numbered placeholders, and ordinary labels like "a servant", "one disciple", "a guard", "the young man", or "the woman".
Do not create group characters such as "cultivation monks", "guards", "disciples", or "servants". Extract individuals only.

appearance_type:
- Use "appeared" only when the character is physically present, speaks, acts, or directly participates.
- Use "mentioned" when the character is only named, remembered, referenced, or discussed.
- Mark "appeared" for current-scene arrival/presence wording such as "X is here", "X arrived", "X entered", "X stood nearby", or "X watched from the side".
- Do not mark "appeared" for absence, rumor, memory, historical reference, future possibility, or comparison wording.
"""

CHARACTER_METADATA_RULES = """
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
Do not extract temporary moods, injuries, locations, or possessions as metadata.
Do not put sect roles, occupations, disciple ranks, social positions, titles, or faction roles in status.
Use faction_or_affiliation for sect/clan/organization membership.
Use titles for stable titles or roles.
Only extract status when there is a meaningful life-status change or special condition.
Do not extract status="alive" merely because a character appears, speaks, fights, or acts.
Only extract status="dead" when death is explicit.
If metadata already exists in memory, do not repeat it unless this chapter provides a clearer or more current durable fact.
"""

ALIAS_RULES = """
ALIASES:
- Include alternate labels used in this chapter: titles, nicknames, partial names, descriptive labels.
- Do not include the canonical name as an alias.
- When a real name is revealed, use the real name as canonical and put the old title/label in aliases.
- Only add an alias when the chapter clearly uses that alias for the same character.

Canonical name priority:
1. Full real name.
2. Stable sect/title name.
3. Stable nickname or recurring label.
4. Honorific-only or localized forms.
5. Generic visual descriptions.

Use the highest-priority name clearly supported by the chapter or memory.
Put lower-priority labels used for the same character into aliases.
If a real name is revealed later, use the real name as canonical and keep old labels as aliases.
"""

PROGRESSION_RULES = """
PROGRESSION:
Any confirmed cultivation, power, realm, rank, stage, layer, grade, class, job, position, title, disciple status, promotion, or breakthrough belongs in progression_events.

A progression_event is required when the chapter confirms:
- a breakthrough, advancement, promotion, rank-up, class/job change, or position change happened
- a current cultivation/power level, realm, stage, rank, layer, grade, position, class, job, title, or status is stated for the first time
- a level/rank is stated after training, meditation, pill/resource use, battle, recovery, awakening, or breakthrough context

Only output progression_events for confirmed current states, breakthroughs, promotions, and durable status changes.
Do NOT output progression_events for near breakthroughs, plans, hopes, requirements, guesses, instructions, future possibilities, unchanged repeated known values, items, rewards, gifts, purchases, resources, temporary possessions, skills, techniques, arts, spells, abilities, artifacts, manuals, books, scrolls, or jade slips.

A realm/level mention alone is NOT sufficient. The text must clearly indicate the character already reached, entered, advanced to, broke through to, became, currently is at, or currently possesses that level/status.
A skill may be acquired, learned, used, or improved, but that is not progression unless the text confirms a durable class, rank, realm, level, job, position, or state changed.

Type boundaries:
- "Were-demon skill", "Flame Serpent Art", "Water Arrow Technique", and similar named skills/arts/techniques are skills, not progression.
- "Bronze Rank", "Level 7", "Foundation Establishment", "Outer Sect disciple", and similar durable ranks/realms/positions are progression.

Strong negative indicators include: can reach, could reach, might reach, maybe, perhaps, almost, close to, nearly, with more, need more, if I, should be able to, would be able to, I think, I believe, soon, not yet, preparing to, attempting to.

If the text first confirms a level/rank/stage/status and later says the character is close to a higher/next/peak level, extract only the confirmed current level, not the near-future one.

PROGRESSION ATTRIBUTION:
Attach the progression only to the character explicitly stated or clearly implied to possess or reach that level/status.
Do not copy one character's cultivation/rank/status onto another character without direct textual support.
If the owner is unclear or ambiguous, do not guess.
"""

PROGRESSION_REASONING_RULES = """
PROGRESSION REASONING:
For each possible cultivation or power change, reason over the local narrative sequence before returning JSON.

Ask:
- Did the character consume pills, resources, spiritual energy, essence, or other advancement materials?
- Did the character's body, aura, eyes, pores, impurities, spiritual energy, cultivation foundation, or power visibly change?
- Did nearby narration or dialogue state a completed level, realm, breakthrough, rank, class, job, position, or promotion?
- Is there a short realization or exclamation such as "The third level of Qi Condensation!" after advancement context?
- Does later narration only say the character is near, close to, almost at, or just short of a higher/peak/next level?

Return a progression_event only for the completed state change.
Use exact raw chapter evidence that directly proves the completed state, preferably the short exclamation plus the immediate advancement context.
Do not use later near-breakthrough wording as the new_value.
If a passage confirms a current level and later says the character is close to that level's peak or next level, extract only the confirmed current level.

Example:
Context: body impurities are expelled, eyes shine, then the character says "The third level of Qi Condensation!"
Later: "just a hair away from peak of the third level"
Return:
new_value: "third level of Qi Condensation"
Do not return:
new_value: "peak of the third level"
"""

SKILL_RULES = """
SKILLS:
Skills are named techniques, spells, abilities, martial arts, cultivation methods, divine abilities, class abilities, or combat moves.

Extract a skill if it is learned, known, used, mastered, created, taught, explained as important, or newly named.
Do not put manuals, pills, artifacts, medicines, treasures, resources, scrolls, or physical objects in skills.
A manual or scroll is an item. Only a named technique inside it is a skill.
Do not extract cultivation realms, ranks, levels, stages, classes, jobs, positions, titles, or disciple statuses as skills.
Realm/rank/position examples such as "Qi Condensation", "Foundation Establishment", "Bronze Rank", "Level 7", or "Outer Sect disciple" are progression states unless the evidence explicitly describes a method, practice, manual, scripture, or technique being learned.
An artifact or item enabling an action is not a skill.

Boundary examples:
- "Qi Condensation" = realm/progression.
- "Qi Condensation Method" = possible skill/method if evidence describes learning or practicing a method.
- "Qi Condensation Manual" = item/manual.
"""

CHARACTER_SKILL_RULES = """
CHARACTER_SKILLS:
Output one character_skills entry when a character clearly has a named skill because they learn, use, know, master, create, or teach it.
If a character_skills entry references a skill not already listed in memory, also output that skill in skills.
Set relationship_type to "has".
Do not repeat a known character-skill relationship from memory. Different action verbs do not create different relationships.
Do not create character_skills entries for items or artifacts, even if the item grants flight, attack, defense, storage, healing, or another effect.
If a character uses a named artifact or physical object, create character_items instead of character_skills.
Only create character_skills when the character personally learns, performs, casts, activates, teaches, knows, or masters a named skill, technique, art, spell, method, or ability.
The evidence must prove the character-skill relationship action. Do not extract a character_skill if the evidence only mentions the skill name nearby.

Examples:
- "Elder Sister Xu used the Wind Pennant to fly" => character_item, not character_skill.
- "Meng Hao used Flame Serpent Art" => character_skill.
"""

ITEM_RULES = """
ITEMS:
Items must be wiki-significant.

Extract artifacts, weapons, cultivation manuals, technique scrolls/manuals, pills, medicines, treasures, named quest items, unique equipment, and recurring plot-critical objects.

Skip ordinary clothing, uniforms, servant robes, food, furniture, rooms, buildings, generic tools, common supplies, ordinary jade slips, direction slips, administrative paperwork, and badges/passes/tokens unless magical, named, recurring, or plot-critical.
Do not extract places, sects, mountains, caves, pavilions, resources, manuals, or items as characters.
Do not extract techniques, arts, spells, abilities, methods, or skills as items unless the evidence clearly says they are physical media.
Physical media examples: manual, book, scroll, jade slip, tome, scripture, written record.

Boundary examples:
- "Flame Serpent Art" used, cast, activated, or performed => skill, not item.
- "Flame Serpent Art manual" => item/manual.
- "Water Arrow Technique" => skill.
- "Water Arrow Technique jade slip" => item.
"""

CHARACTER_ITEM_RULES = """
CHARACTER_ITEMS:
Output one character_items entry when a character clearly has a meaningful relationship to a wiki-significant item because they own it, obtain it, receive it, give it, lose it, or use it in a meaningful way.

Allowed relationship_type values:
- owns
- obtained
- used
- lost
- gave
- received

If a character_items entry references an item not already listed in memory, also output that item in items.
Do not create character_items entries for generic possessions, clothing, rooms, paperwork, or ordinary supplies.
Do not repeat a known character-item relationship from memory unless this chapter changes the relationship type or adds durable new information.
If the owner/user is unclear, still return the item if significant, but omit the relationship.
The evidence must prove both the character/item attribution and the exact relationship action.
- obtained/received evidence must show the character actually got, took, received, accepted, picked up, acquired, was given, or ended up possessing the specific item.
- gave evidence must show transfer from that character to another.
- used evidence must show actual use, not intent or preparation.
- lost evidence must show the item was actually lost, stolen, destroyed, handed over, taken away, or no longer possessed.
- owns evidence must show clear possession or ownership.
Do not extract the relationship if evidence only mentions the item, shows the item appearing, mentions a demand/threat, describes nearby scene movement, or uses vague possession like "treasures" without naming the specific item.
"""

LIFE_EVENT_RULES = """
LIFE EVENTS:
life_events are only for hard status changes:
- death
- fake_death
- resurrection
- body_destroyed
- soul_survived
- sealed

Do not create life_events for injury, fear, being trapped, being captured, being rescued, confusion, uncertain future, or temporary danger.
"""

EVENTS_DISABLED_RULES = """
Timeline events are disabled for now.
Always return "events": [].
Do not put cultivation breakthroughs, rank changes, deaths, fake deaths, resurrections, body/soul changes, item acquisitions, skill acquisitions, location arrivals, or battles in events.
"""

FINAL_CHECK_RULES = """
FINAL CHECK BEFORE JSON:
1. Resolve aliases inside the chapter.
2. Use canonical names from memory when supported.
3. Check every character for confirmed cultivation/power/rank/status changes.
4. Check every skill and character_skill description for hidden progression facts.
5. Make sure all confirmed progression facts have matching progression_events.
6. Make sure events is always [].
7. Make sure all evidence excerpts are exact raw chapter text and directly relevant.
"""


def compose_prompt(*sections):
    return "\n\n".join(section.strip() for section in sections if section).strip()


CHARACTER_EXTRACTION_PROMPT = compose_prompt(
    "You extract ONLY character identity, aliases, and durable character metadata from Asian cultivation and LitRPG novel chapters.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: characters.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    CHARACTER_RULES,
    CHARACTER_METADATA_RULES,
    ALIAS_RULES,
)

PROGRESSION_EXTRACTION_PROMPT = compose_prompt(
    "You extract ONLY confirmed character progression from Asian cultivation and LitRPG novel chapters.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: progression_events.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    PROGRESSION_RULES,
)

PROGRESSION_REASONING_PROMPT = compose_prompt(
    "You perform focused reasoning ONLY for indirect confirmed character progression in Asian cultivation and LitRPG novel chapters.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: progression_events.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    PROGRESSION_RULES,
    PROGRESSION_REASONING_RULES,
)

SKILL_EXTRACTION_PROMPT = compose_prompt(
    "You extract ONLY skills and character-skill relationships from Asian cultivation and LitRPG novel chapters.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: skills and character_skills.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    SKILL_RULES,
    CHARACTER_SKILL_RULES,
)

ITEM_EXTRACTION_PROMPT = compose_prompt(
    "You extract ONLY wiki-significant items and character-item relationships from Asian cultivation and LitRPG novel chapters.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: items and character_items.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    ITEM_RULES,
    CHARACTER_ITEM_RULES,
)

LIFE_EVENT_EXTRACTION_PROMPT = compose_prompt(
    "You extract ONLY hard character life-status events from Asian cultivation and LitRPG novel chapters.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: life_events.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    LIFE_EVENT_RULES,
)

PROGRESSION_AUDIT_PROMPT = compose_prompt(
    "You perform a second-pass audit focused ONLY on character power progression.",
    JSON_OUTPUT_RULES,
    "Return JSON containing only: progression_events. Do not extract characters, skills, items, character_skills, life_events, locations, or timeline events.",
    GENERAL_RULES,
    EVIDENCE_RULES,
    MEMORY_RULES,
    PROGRESSION_RULES,
    """
Audit job:
- Catch progression facts the first pass may have missed.
- Scan short realization/exclamation sentences after training, meditation, pill use, resource use, battle, recovery, or awakening.
- Return only confirmed progression_events.
""",
)

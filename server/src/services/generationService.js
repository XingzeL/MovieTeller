const ALLOWED_LEVELS = [
  "A1",
  "A2",
  "B1",
  "B2",
  "C1",
  "IELTS",
  "TOEFL",
  "CET-4",
  "CET-6",
  "专四",
  "专八",
  "考研",
];

const NARRATION_BY_LEVEL = {
  A1: "A man is walking in a park.",
  A2: "A man is walking slowly through a quiet park on a sunny day.",
  B1: "A man walks through the park, enjoying the fresh air and green trees around him.",
  B2: "A man strolls through a peaceful park, enjoying the calm atmosphere.",
  C1: "Bathed in soft afternoon light, a solitary figure meanders along winding paths, savoring the park's tranquil rhythm and the subtle interplay of shadow and foliage.",
  IELTS:
    "Overall, the scene depicts an individual walking through a public park in calm weather; the focus is on simple, natural movement and the peaceful outdoor setting.",
  TOEFL:
    "The passage implies that the subject's movement through the park serves as a representative instance of leisure behavior in an urban green space, linking pedestrian activity to environmental context.",
  "CET-4":
    "There is a man in the park. He is walking. The weather is nice and the trees are green.",
  "CET-6":
    "A man is walking in the park, enjoying the sunshine and the fresh air on a pleasant afternoon.",
  专四:
    "A young man walks through the park at an easy pace, taking in the greenery and the mild afternoon breeze.",
  专八:
    "With measured steps, he traverses the tree-lined paths, attuned to the park's muted symphony of rustling leaves and distant footsteps.",
  考研:
    "Far from a mere commute across green space, his walk unfolds as a deliberate encounter with texture—light, sound, and tempo—turning an ordinary afternoon into a quiet study in urban respite.",
};

/**
 * Mock scene narration by selected difficulty labels (CEFR / IELTS & TOEFL / China exams). Replace with real AI later.
 * @param {{ levels: string[], inputHint?: string }} opts
 * @returns {Record<string, string>}
 */
export function generateMockNarration({ levels, inputHint = "" }) {
  const results = {};
  const hint = inputHint ? ` (source: ${inputHint})` : "";
  for (const level of levels) {
    const base = NARRATION_BY_LEVEL[level];
    if (base) {
      results[level] = base + hint;
    }
  }
  return results;
}

export { ALLOWED_LEVELS };

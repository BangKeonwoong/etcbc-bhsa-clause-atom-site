# ETCBC/BHSA official seed notes

## Directly grounded in published docs

- `conjunction_classes`: seeded from the BHSA `code` page examples for coordinate, postulational, conditional, and final opening conjunction classes.
- `preposition_classes`: seeded from the BHSA `code` page examples for temporal/causal opening-preposition classes.
- `infinitive_preposition_classes`: seeded from the BHSA `code` page table for infinitive-construct preposition classes.
- `relative_lexemes`: seeded with `>CR` because the `syn04types` manual lists it among internal lexemes and the BHSA docs tie relative openings to `Rela`/relative clauses.

## Cautious starter inferences

- `quote_verbs`: `>MR[`, `DBR[`, `NGD[` are used as verbum-dicendi starter verbs.
- `object_clause_governors`: the starter set adds `JD<[`, `R>H[`, `CM<[` to the speech verbs because these knowledge/perception verbs are listed as program-internal in `syn04types`. This is heuristic, not a recovered ETCBC gold list.
- `subject_clause_governors` and `predicative_clause_governors` are left empty on purpose because the published manuals do not give stable lexeme tables for them.

## Not seeded

- No explicit causal conjunction lexemes for class 900, because the published BHSA page shows the class range but does not publish example lexemes for that class.
- No conjunctive-adverb lexeme table for code class 300, because the published docs describe the class but do not expose a canonical lexeme list.


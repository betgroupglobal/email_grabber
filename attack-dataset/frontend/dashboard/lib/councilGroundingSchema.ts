import { z } from "zod";
import { AttackChainSchema } from "@/lib/liveCouncilSchema";

export const DatasetHitSchema = z
  .object({
    id: z.union([z.string(), z.number()]).optional(),
    title: z.string().optional(),
    category: z.string().optional(),
    attack_type: z.string().optional(),
    mitre_technique: z.string().optional(),
    tools_used: z.string().optional(),
    score: z.number().optional(),
    ml_category: z.string().optional(),
    ml_confidence: z.number().optional(),
  })
  .passthrough();

export const MlPredictionSchema = z
  .object({
    label: z.string().optional(),
    confidence: z.number().optional(),
  })
  .passthrough();

/** Per-turn grounding pack from Knowledge Engine (`buildCouncilGroundingPack`). */
export const CouncilGroundingPackSchema = z
  .object({
    turn: z.number(),
    built_at: z.string().optional(),
    query_text: z.string(),
    dataset_hits: z.array(DatasetHitSchema).optional(),
    ml_predictions: z.array(MlPredictionSchema).optional(),
    similar_chains_hint: z.unknown().optional(),
    replan_candidates: z.array(AttackChainSchema).optional(),
    alternate_chain_scores: z.array(z.number()).optional(),
    model_metadata: z
      .object({
        embedding_model: z.string().optional(),
        ml_model_name: z.string().optional(),
        dataset_source: z.string().optional(),
        dataset_version: z.string().optional(),
      })
      .passthrough()
      .optional(),
    errors: z
      .object({
        search: z.string().nullable().optional(),
        ml: z.string().nullable().optional(),
      })
      .optional(),
  })
  .passthrough();

export type CouncilGroundingPack = z.infer<typeof CouncilGroundingPackSchema>;
export type DatasetHit = z.infer<typeof DatasetHitSchema>;
export type MlPrediction = z.infer<typeof MlPredictionSchema>;

export function parseCouncilGroundingPack(input: unknown) {
  return CouncilGroundingPackSchema.safeParse(input);
}

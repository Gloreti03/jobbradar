import type { Profile, ProfileAnswers, ProfileOut, ProfileUpdate } from "@/types";
import { DISCOVERY_QUESTIONS } from "./profile-material";

interface ProfileClient {
  updateProfile(body: ProfileUpdate): Promise<ProfileOut>;
  answerProfile(body: ProfileAnswers): Promise<ProfileOut>;
}

export async function saveProfileWithAnswers(
  client: ProfileClient,
  profile: Profile,
  extraText: string,
  answers: Record<number, string>,
  discovery: Record<number, string>,
  questions: string[] = profile.missing_info,
) {
  const missingAnswers = questions.flatMap((question, i) => {
    const answer = answers[i]?.trim();
    return answer ? [{ question, answer }] : [];
  });
  const discoveryAnswers = DISCOVERY_QUESTIONS.flatMap((question, i) => {
    const answer = discovery[i]?.trim();
    return answer ? [{ question, answer }] : [];
  });
  const submitted = [...missingAnswers, ...discoveryAnswers];
  // Register answered discovery questions in missing_info first, as required by
  // the backend contract. Preserve existing questions until POST /answers succeeds.
  const draft = {
    ...profile,
    missing_info: [...new Set([...profile.missing_info, ...submitted.map((a) => a.question)])],
  };
  const saved = await client.updateProfile({ profile: draft, extra_text: extraText });
  return submitted.length ? client.answerProfile({ answers: submitted }) : saved;
}

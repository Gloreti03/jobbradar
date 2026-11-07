import regularUrl from "@/assets/fonts/Vera.ttf?url";
import boldUrl from "@/assets/fonts/VeraBd.ttf?url";
import { createCoverPdf, createCVPdf, pdfFilename } from "./document-pdf";
import type { PdfFonts } from "./document-pdf";
import type { TailoredCV } from "@/types";

let fontsPromise: Promise<PdfFonts> | undefined;
async function fontBase64(url: string) {
  const response = await fetch(url);
  if (!response.ok) throw new Error("Could not load PDF fonts. Please try again.");
  const bytes = new Uint8Array(await response.arrayBuffer());
  let binary = "";
  for (let i = 0; i < bytes.length; i += 8192) binary += String.fromCharCode(...bytes.subarray(i, i + 8192));
  return btoa(binary);
}

export async function downloadPdf(kind: "cv" | "cover", cv: TailoredCV, letter: string, company: string | null) {
  fontsPromise ??= Promise.all([fontBase64(regularUrl), fontBase64(boldUrl)])
    .then(([regular, bold]) => ({ regular, bold }))
    .catch((error) => { fontsPromise = undefined; throw error; });
  const fonts = await fontsPromise;
  const doc = kind === "cv" ? createCVPdf(cv, fonts) : createCoverPdf(cv, letter, fonts);
  await doc.save(pdfFilename(cv.name, company, kind), { returnPromise: true });
}

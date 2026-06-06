const { createWorker } = require("tesseract.js");

async function main() {
  const imagePath = process.argv[2];
  const languages = process.argv[3] || "eng";
  if (!imagePath) {
    throw new Error("Image path is required.");
  }

  let worker;
  try {
    worker = await createWorker(languages);
  } catch (error) {
    if (languages !== "eng") {
      worker = await createWorker("eng");
    } else {
      throw error;
    }
  }

  try {
    const result = await worker.recognize(imagePath);
    process.stdout.write(result?.data?.text || "");
  } finally {
    await worker.terminate();
  }
}

main().catch((error) => {
  process.stderr.write(error?.message || String(error));
  process.exit(1);
});

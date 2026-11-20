// Mano Clip Tool: run Whisper away from the page UI thread.
let transcriberPromise = null;

async function getTranscriber() {
  if (!transcriberPromise) {
    transcriberPromise = (async () => {
      const { pipeline } = await import('https://cdn.jsdelivr.net/npm/@huggingface/transformers@3.7.2');
      return pipeline(
        'automatic-speech-recognition',
        'onnx-community/whisper-tiny.en',
        { dtype: 'q8' }
      );
    })();
  }
  try {
    return await transcriberPromise;
  } catch (error) {
    transcriberPromise = null;
    throw error;
  }
}

self.onmessage = async (event) => {
  const message = event.data || {};
  if (message.type !== 'transcribe') return;

  try {
    self.postMessage({ type: 'progress', percent: 18, title: 'Loading compact speech model…', detail: 'The first use downloads a small model into your browser cache' });
    const transcriber = await getTranscriber();
    self.postMessage({ type: 'progress', percent: 38, title: 'Listening to the full video…', detail: 'Speech is processed in short overlapping sections' });

    const audio = message.audio instanceof Float32Array
      ? message.audio
      : new Float32Array(message.audio);
    const result = await transcriber(audio, {
      sampling_rate: message.sampleRate || 16000,
      chunk_length_s: 20,
      stride_length_s: 4,
      return_timestamps: true
    });

    const chunks = (result && result.chunks) ? result.chunks : [];
    if (!chunks.length && result && result.text) {
      chunks.push({ timestamp: [0, message.duration || 0], text: result.text });
    }
    self.postMessage({ type: 'result', chunks, duration: message.duration || 0 });
  } catch (error) {
    self.postMessage({
      type: 'error',
      message: error && error.message ? error.message : String(error)
    });
  }
};

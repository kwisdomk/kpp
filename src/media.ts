/** Convert browser-decoded audio to the backend's bounded canonical WAV format. */
export async function audioToWav(file: File): Promise<File> {
  if (file.size > 8 * 1024 * 1024) throw new Error("Audio upload exceeds 8 MiB.");
  const context = new AudioContext({ sampleRate: 16000 });
  try {
    const decoded = await context.decodeAudioData(await file.arrayBuffer());
    if (!decoded.length || decoded.duration > 60) {
      throw new Error("Use an audio recording between zero and 60 seconds.");
    }
    const bytes = new ArrayBuffer(44 + decoded.length * 2);
    const view = new DataView(bytes);
    const writeText = (offset: number, text: string) => {
      for (let i = 0; i < text.length; i++) view.setUint8(offset + i, text.charCodeAt(i));
    };
    writeText(0, "RIFF");
    view.setUint32(4, bytes.byteLength - 8, true);
    writeText(8, "WAVEfmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, 1, true);
    view.setUint32(24, decoded.sampleRate, true);
    view.setUint32(28, decoded.sampleRate * 2, true);
    view.setUint16(32, 2, true);
    view.setUint16(34, 16, true);
    writeText(36, "data");
    view.setUint32(40, decoded.length * 2, true);
    const channels = Array.from({ length: decoded.numberOfChannels }, (_, channel) => decoded.getChannelData(channel));
    for (let index = 0; index < decoded.length; index++) {
      const average = channels.reduce((sum, channel) => sum + channel[index], 0) / channels.length;
      const sample = Math.max(-1, Math.min(1, average));
      view.setInt16(44 + index * 2, Math.round(sample * (sample < 0 ? 32768 : 32767)), true);
    }
    return new File([bytes], "question.wav", { type: "audio/wav" });
  } finally {
    await context.close();
  }
}

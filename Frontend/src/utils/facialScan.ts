export const startFacialScan = async (): Promise<boolean> => {
  return new Promise((resolve) => {
    setTimeout(() => resolve(true), 300);
  });
};

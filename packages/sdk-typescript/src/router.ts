export function chooseVariant(split: number): "variant" | "baseline" {
  return Math.random() < split ? "variant" : "baseline";
}

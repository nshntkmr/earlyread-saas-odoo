import fs from "node:fs/promises";
import { FileBlob, PresentationFile } from "@oai/artifact-tool";

const STARTER = "C:/Users/nisha/Odoo_Dev/work/presentations/posterra-azure-client-demo/tmp/template-starter.pptx";
const FINAL = "C:/Users/nisha/Odoo_Dev/outputs/posterra_azure_cost_and_product_demo.pptx";
const PREVIEW_DIR = "C:/Users/nisha/Odoo_Dev/work/presentations/posterra-azure-client-demo/tmp/preview";
const LAYOUT_DIR = "C:/Users/nisha/Odoo_Dev/work/presentations/posterra-azure-client-demo/tmp/layout/final";

async function writeBlob(path, blob) {
  await fs.writeFile(path, new Uint8Array(await blob.arrayBuffer()));
}

function setText(shape, text, style = {}) {
  shape.text = text;
  if (style && Object.keys(style).length) {
    shape.text.style = style;
  }
  return shape;
}

async function main() {
  await fs.mkdir(PREVIEW_DIR, { recursive: true });
  await fs.mkdir(LAYOUT_DIR, { recursive: true });
  await fs.mkdir("C:/Users/nisha/Odoo_Dev/outputs", { recursive: true });

  const presentation = await PresentationFile.importPptx(await FileBlob.load(STARTER));
  const slide1Shapes = presentation.slides.items[0].shapes.items;
  const slide2Shapes = presentation.slides.items[1].shapes.items;

  // Slide 1: Azure cost estimate.
  setText(
    slide1Shapes[1],
    "Azure Dev Environment: Expected Monthly Run Rate",
    { fontSize: 38, bold: false, color: "#000000" },
  );
  setText(slide1Shapes[0], "1", { fontSize: 14, color: "#000000", alignment: "right" });
  setText(
    slide1Shapes[15],
    "Estimate based on the current Dev infrastructure-as-code in Azure eastus2: private network, managed PostgreSQL, file storage, secrets vault, AKS runtime, gateway, certificate automation, and shared image registry. Rounded for planning; actual spend varies with uptime, logs, traffic, backups, and discounts.",
    { fontSize: 20, color: "#000000" },
  );

  setText(slide1Shapes[4], "~$580", { fontSize: 58, bold: false, color: "#000000" });
  setText(slide1Shapes[5], "Dev baseline\nper month", { fontSize: 18, color: "#000000" });

  setText(slide1Shapes[7], "$140", { fontSize: 58, bold: false, color: "#000000" });
  setText(slide1Shapes[8], "Each core\nsystem node", { fontSize: 18, color: "#000000" });

  setText(slide1Shapes[10], "$70", { fontSize: 58, bold: false, color: "#000000" });
  setText(slide1Shapes[11], "Each extra\napp node", { fontSize: 18, color: "#000000" });

  setText(slide1Shapes[13], "$20", { fontSize: 58, bold: false, color: "#000000" });
  setText(slide1Shapes[14], "Shared registry\nplus state", { fontSize: 18, color: "#000000" });

  // Slide 2: product strengths for client demo.
  setText(
    slide2Shapes[4],
    "Client Demo: Configurable Healthcare Analytics Suite",
    { fontSize: 36, bold: false, color: "#000000" },
  );
  setText(slide2Shapes[3], "2", { fontSize: 14, color: "#000000", alignment: "right" });

  setText(
    slide2Shapes[5],
    "White-label, multi-app portal\nEach client can have its own branding, login, navigation, pages, tabs, widgets, and filters without new engineering work.",
    { fontSize: 22, color: "#000000" },
  );
  setText(
    slide2Shapes[6],
    "Strong RBAC and data scoping\nUsers are limited by app role, security group, and assigned provider or agency scope, with security-ready audit patterns for regulated data.",
    { fontSize: 22, color: "#000000" },
  );
  setText(
    slide2Shapes[7],
    "Analytics workbench built in\nAdmins can register data sources, build widgets, use safe query generation, and demo KPIs, charts, maps, tables, drilldowns, and saved comparisons.",
    { fontSize: 22, color: "#000000" },
  );

  for (const [index, slide] of presentation.slides.items.entries()) {
    const stem = `slide-${String(index + 1).padStart(2, "0")}`;
    await writeBlob(`${PREVIEW_DIR}/${stem}.png`, await presentation.export({ slide, format: "png", scale: 1 }));
    const layout = await slide.export({ format: "layout" });
    await fs.writeFile(`${LAYOUT_DIR}/${stem}.layout.json`, await layout.text());
  }
  await writeBlob(`${PREVIEW_DIR}/deck-montage.webp`, await presentation.export({ format: "webp", montage: true, scale: 1 }));

  const inspect = await presentation.inspect({ kind: "slide,textbox,shape,table,chart,image", maxChars: 20000 });
  await fs.writeFile("C:/Users/nisha/Odoo_Dev/work/presentations/posterra-azure-client-demo/tmp/qa/final-inspect.ndjson", inspect.ndjson || "", "utf8");

  const pptx = await PresentationFile.exportPptx(presentation);
  await pptx.save(FINAL);
  console.log(FINAL);
}

main().catch((error) => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});

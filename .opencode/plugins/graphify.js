// graphify OpenCode plugin
// Injects a knowledge graph reminder before bash tool calls when the graph exists.
import { existsSync } from "fs";
import { join } from "path";

export const GraphifyPlugin = async ({ directory }) => {
  let reminded = false;

  return {
    "tool.execute.before": async (input, output) => {
      if (reminded) return;
      if (!existsSync(join(directory, "graphify-out", "graph.json"))) return;

      if (input.tool === "bash") {
        // Prefix the command with a knowledge graph reminder.
        // Use semicolon (works on both Unix sh and Windows PowerShell)
        // instead of && (which fails in PowerShell).
        // Avoid bare `<` (redirect) in the injected text.
        const reminder =
          "[graphify] knowledge graph at graphify-out/. For focused questions, use: graphify query <question>";
        output.args.command = `echo "${reminder}"; ${output.args.command}`;
        reminded = true;
      }
    },
  };
};

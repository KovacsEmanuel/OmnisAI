// Supervised server entry: no installer, init, cloud or model driver.
import { startDaemon } from '@reticlehq/server';
const running = await startDaemon({
  port: Number(process.env.RETICLE_PORT),
  host: '127.0.0.1',
  token: process.env.RETICLE_TOKEN,
  headless: true,
  reticleRoot: `${process.cwd()}/.reticle`,
});
process.stdout.write(JSON.stringify({event: 'probe_server_ready', port: Number(process.env.RETICLE_PORT)}) + '\n');
let closing = false;
async function close() {
  if (closing) return;
  closing = true;
  await running.close();
  process.stdout.write(JSON.stringify({event: 'probe_server_closed'}) + '\n');
  process.exit(0);
}
process.on('SIGTERM', close);
process.on('SIGINT', close);

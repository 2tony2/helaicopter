class Helaicopter < Formula
  desc "Browse local Claude Code, Codex, and OpenClaw conversations"
  homepage "https://github.com/2tony2/helaicopter"
  head "https://github.com/2tony2/helaicopter.git", branch: "main"

  depends_on "node"
  depends_on "python@3.13"
  depends_on "uv"

  def install
    libexec.install Dir["*"]

    launcher = libexec/"packaging/homebrew/launcher.py"
    chmod 0755, launcher

    bin.write_env_script launcher,
                         HELAICOPTER_STAGED_ROOT: opt_libexec,
                         PATH: "#{Formula["node"].opt_bin}:#{Formula["python@3.13"].opt_bin}:#{Formula["uv"].opt_bin}:#{ENV["PATH"]}"
  end

  service do
    run [opt_bin/"helaicopter", "serve"]
    keep_alive true
    environment_variables PATH: std_service_path_env
    log_path var/"log/helaicopter.log"
    error_log_path var/"log/helaicopter.log"
  end

  test do
    assert_match "\"staged_root\":", shell_output("#{bin}/helaicopter paths")
  end
end

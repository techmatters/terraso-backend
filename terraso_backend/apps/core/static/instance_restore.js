(function () {

  const button = document.getElementById("restore-button");
  const statusP = document.getElementById("restore-status");

  function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
  const csrfToken = getCookie('csrftoken');

  const headers = {
    "X-CSRFToken": csrfToken
  };

  const setError = () => {
    statusP.textContent = "Error replacing data. Please check logs.";
  };

  function checkJobDone(taskId, resolve, reject) {
    return () => {
      fetch(`/admin/restore/jobs/${taskId}`, { headers })
        .then(resp => {
          if (!resp.ok) {
            reject();
          }
          return resp.json();
        }).then((json) => {
          const { status } = json;
          if (status === "failed") {
            reject();
          } else if (status === "finished") {
            resolve();
          }
        });
    }
  }

  button.addEventListener("click", async () => {
    const resp = await fetch("/admin/restore", { method: "POST", headers });
    if (!resp.ok) {
      setError();
    }
    const { taskId } = await resp.json();
    statusP.textContent = "Job triggered";

    let intervalId = null;

    new Promise((resolve, reject) => {
      const f = checkJobDone(taskId, resolve, reject);
      intervalId = setInterval(f, 5000);
    }).then(() => {
      statusP.textContent = "Job finished successfully.";
    }).catch(() => {
      setError();
    }).finally(() => {
      if (intervalId) {
        clearInterval(intervalId);
      }
    });

  });
})();

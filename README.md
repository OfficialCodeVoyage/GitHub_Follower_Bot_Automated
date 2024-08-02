# GitHub Follower Bot Automated

Welcome to the **GitHub Follower Bot Automated** repository! This project is designed to help you automatically follow your GitHub followers, keeping your network growing and engaged with minimal effort.

**You Follow Me** ---> **My Bot Follows you Back! Let's growth Together!**

## 📝 Usage

The bot will fetch your list of followers and automatically follow any users that are not already followed.
A log of followed users is maintained in the `followers.txt` file.
The bot will continue to run until all followers have been processed.

The bot can be run in two ways:
1. **[Manually](#run-the-bot-manually)**: You can run the bot manually on your local machine.
2. **[Automatically with GitHub Actions](#github-actions-workflow-setup)**: Set up the bot to run automatically on a schedule using GitHub Actions.


## 🚀 Features

- **Automated Follower Management:** Automatically follows users who follow you on GitHub.
- **User-Friendly:** Easy to set up and run, even for those with minimal technical knowledge.
- **Error Handling:** Built-in error handling ensures smooth operation and reliability.
- **Logging:** Detailed logs for tracking bot activity and performance.


## 🛠️ Setup & Installation To Run the Bot Manually on Local Server
### Run the Bot Manually

### 1. Clone the Repository
Clone this repository to your local machine:
```bash
git clone https://github.com/OfficialCodeVoyage/GitHub_Follower_Bot_Automated.git
cd GitHub_Follower_Bot_Automated
```

### 2. Install Dependencies
Install the required Python packages using pip:
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a .env file in the project root and add your GitHub username and Personal Access Token:
```bash
GITHUB_USER=your_github_username
PERSONAL_GITHUB_TOKEN=your_personal_access_token
```
**Make sure you do not commit this file to the repository as it contains sensitive information.**

### 4. Run the Bot
Run the bot using the following command:
```bash
python follower_bot.py
```

## 🛠️ Setup & Installation To Run the Bot every 10 minutes with GitHub Actions(Automatically)
### GitHub Actions Workflow Setup
<p>To set up the bot to run automatically on a schedule using GitHub Actions, follow these steps:</p>

<h4>1. Creating a Personal Access Token (PAT):</h4>

<ol>
    <li><strong>Go to GitHub Settings:</strong> Navigate to your GitHub profile, click on your avatar in the upper-right corner, and select "Settings".</li>
    <li><strong>Access Developer Settings:</strong> On the left sidebar, click on "Developer settings"(all the way to bottom / last button). Under "Developer settings", click on "Personal access tokens".</li>
    <li><strong>Generate a New Token:</strong> Click the "Generate new token" button. Give your token a descriptive name like "GitHub Follower Bot Token".</li>
    <li><strong>Select the Required Scopes:</strong> Choose the following scopes:
        <ul>
            <li><code>repo</code>: Full control of private repositories.</li>
            <li><code>workflow</code>: Update GitHub Actions workflows.</li>
            <li><code>admin:repo_hook</code>: Manage webhooks and their events.</li>
            <li><code>public_repo</code>: Access to public repositories.</li>
            <li><code>read:user</code>: Read access to profile data.</li>
            <li><code>write:repo_hook</code>: Manage repository hooks.</li>
            <li><code>user</code>: Read and write access to profile information.</li>
            <li><code>gist</code>: Access to Gists (if needed).</li>
        </ul>
    </li>
    <li><strong>Generate and Save the Token:</strong> Click "Generate token" and <strong>copy the token</strong> immediately, as it will not be shown again.</li>
</ol>

<h4>2. Storing the PAT as a GitHub Secret:</h4>

<ol>
    <li><strong>Navigate to Your Repository:</strong> Go to your repository on GitHub. Click on "Settings" in the repository menu.</li>
    <li><strong>Add a New Secret:</strong> On the left sidebar, click on "Secrets and variables" under the "Security" section and select "Actions". Click "New repository secret".</li>
    <li><strong>Name the secret <code>PERSONAL_GITHUB_TOKEN</code>:</strong> Paste the Personal Access Token you copied earlier into the "Secret" field and click "Add secret" to save it.</li>
</ol>

<h4>3. Updating the GitHub Actions Workflow File:</h4>

<p>In your YAML file (e.g., <code>automation.yml</code>), update the following:</p>

<ol>
    <li><strong>Token Reference:</strong> Ensure your workflow is referencing the token correctly:
        <pre><code>env:
  GITHUB_TOKEN: ${{ secrets.PERSONAL_GITHUB_TOKEN }}</code></pre>
    </li>
    <li><strong>Script Name:</strong> Replace <code>bot.py</code> with your actual script name in the <code>run</code> command:
        <pre><code>run: |
  python bot.py</code></pre>
    </li>
    <li><strong>Dependencies:</strong> Make sure your <code>requirements.txt</code> is correct and that the path is correct if it's in a different directory.</li>
    <li><strong>Cron Schedule:</strong> Adjust the cron expression to control when the workflow runs automatically:
        <pre><code>schedule:
  - cron: '0 0 * * *'  # Modify as needed</code></pre>
    </li>
</ol>

<h4>4. Monitoring the Workflow:</h4>

<ul>
    <li>After setting up, monitor the workflow in the "Actions" tab of your repository to ensure it runs as expected.</li>
</ul>


<ol start="4">
    <li>Commit and push the file to your repository.</li>
</ol>

<h4>4. Granting Workflow Permissions:</h4>

<p>Ensure that your workflow has the necessary permissions by adding this to your YAML file:</p>

<pre><code>permissions:
  contents: write  # Allows committing and pushing changes
  issues: write    # Allows creating and managing issues
  pull-requests: write  # Allows managing pull requests
  workflows: write  # Allows updating GitHub Actions workflows
</code></pre>

<h4>5. Monitoring the Workflow:</h4>

<ul>
    <li>You can monitor the workflow runs in the "Actions" tab of your GitHub repository.</li>
    <li>The bot will run automatically based on the schedule you set or manually from the Actions tab.</li>
</ul>

## 🤖 Bot Configuration

### Environment Variables
- `GITHUB_USER`: Your GitHub username.
- `PERSONAL_GITHUB_TOKEN`: Your GitHub Personal Access Token for API access.

### Optional Features
Additional features can be implemented as needed. Check the Issues and Discussions sections for ideas and contributions.

## 📂 Project Structure

- **bot.py**: Main script for the bot.
- **followers.txt**: File where followed users are logged.
- **requirements.txt**: Python dependencies.
- **.env**: Environment variables (not included, must be created).
- **LICENSE**: Project licensing information.
- **README.md**: This readme file.
- **follower_counter.txt**: total followers that bot followed automatically 

## 📈 Contributions

Contributions are welcome! Feel free to submit a pull request or open an issue for suggestions, bug reports, or feature requests.

### To Contribute:
1. Fork the repository.
2. Create a new branch (`git checkout -b dev`).
3. Make your changes.
4. Commit your changes (`git commit -m 'Add some feature'`).
5. Push to the branch (`git push origin dev`).
6. Open a pull request.

## 🔒 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for more details.

## 📞 Support

For any questions or issues, please feel free to reach out via GitHub Issues or Discussions.




